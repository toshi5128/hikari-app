# 狙いの年代のマス(100m)ごとに、国土地理院ベクトルタイル(z16 building)の建物の数を数える
import json, math, os, sys, urllib.request, collections, time
from concurrent.futures import ThreadPoolExecutor
import mapbox_vector_tile as M
S = os.path.dirname(os.path.abspath(__file__))
APP = r"C:\Users\st106\hikari-app-src"
CACHE = os.path.join(S, "bv"); os.makedirs(CACHE, exist_ok=True)
def tky2jgd(lat, lon):
    return (lat - 0.00010695*lat + 0.000017464*lon + 0.0046017, lon - 0.000046038*lat - 0.000083043*lon + 0.010040)
def jgd2tky(lat, lon):
    a = tky2jgd(lat, lon); return (lat-(a[0]-lat), lon-(a[1]-lon))
def cellof(lat, lng):
    t = jgd2tky(lat, lng); return (int(math.floor(t[0]*1200)), int(math.floor((t[1]-100)*800)))
Z = 16; N = 2**Z
def tileof(lat, lon):
    return int((lon+180)/360*N), int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*N)
def t2ll(x, y):
    lon = x/N*360-180; lat = math.degrees(math.atan(math.sinh(math.pi*(1-2*y/N)))); return lat, lon
tk = json.load(open(os.path.join(APP, "takuchi-nendai-2.json"), encoding="utf-8"))
cells = set()
for rec in tk["clusters"]:
    for o in rec[3]: cells.add((rec[1]+o[0], rec[2]+o[1]))
tiles = set()
for r, c in cells:
    for fr, fc in ((.05, .05), (.95, .05), (.05, .95), (.95, .95)):
        la, lo = tky2jgd((r+fr)/1200, 100+(c+fc)/800); tiles.add(tileof(la, lo))
print("cells", len(cells), "tiles", len(tiles), flush=True)
def fetch(t):
    fn = os.path.join(CACHE, f"{t[0]}_{t[1]}.pbf")
    if os.path.exists(fn): return
    for k in range(4):
        try:
            b = urllib.request.urlopen(f"https://cyberjapandata.gsi.go.jp/xyz/experimental_bvmap/{Z}/{t[0]}/{t[1]}.pbf", timeout=40).read()
            open(fn, "wb").write(b); return
        except urllib.error.HTTPError as e:
            if e.code == 404: open(fn, "wb").write(b""); return
            time.sleep(2)
        except Exception:
            time.sleep(2)
done = 0
with ThreadPoolExecutor(8) as ex:
    for _ in ex.map(fetch, sorted(tiles)):
        done += 1
        if done % 500 == 0: print("fetched", done, flush=True)
cnt = collections.Counter(); small = collections.Counter(); big = collections.Counter()
for t in tiles:
    fn = os.path.join(CACHE, f"{t[0]}_{t[1]}.pbf")
    if not os.path.exists(fn) or os.path.getsize(fn) == 0: continue
    d = M.decode(open(fn, "rb").read())
    L = d.get("building")
    if not L: continue
    ext = L.get("extent", 4096)
    la0, lo0 = t2ll(t[0], t[1]); la1, lo1 = t2ll(t[0]+1, t[1]+1)
    mx = (lo1-lo0)*91000/ext; my = (la0-la1)*111000/ext   # 1単位あたりのm(概算)
    for f in L["features"]:
        g = f["geometry"]
        ring = None
        if g["type"] == "Polygon": ring = g["coordinates"][0]
        elif g["type"] == "MultiPolygon": ring = g["coordinates"][0][0]
        if not ring: continue
        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
        A = 0
        for i in range(len(ring)):
            A += ring[i-1][0]*ring[i][1] - ring[i][0]*ring[i-1][1]
        area = abs(A)/2*mx*my
        cx, cy = sum(xs)/len(xs), sum(ys)/len(ys)   # MVTは y が下向き(decode後は上向き)
        lon = lo0 + (lo1-lo0)*cx/ext; lat = la1 + (la0-la1)*cy/ext
        k = cellof(lat, lon)
        if k not in cells: continue
        cnt[k] += 1
        if 30 <= area <= 250: small[k] += 1
        if area > 400: big[k] += 1
json.dump({f"{k[0]},{k[1]}": [cnt[k], small[k], big[k]] for k in cells}, open(os.path.join(S, "bldg_cells.json"), "w"))
h = collections.Counter(min(small[k] // 5 * 5, 50) for k in cells)
print("戸建てサイズの建物数/マス 分布:", sorted(h.items()), flush=True)
print("DONE", flush=True)
