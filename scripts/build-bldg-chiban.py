# -*- coding: utf-8 -*-
"""
build-bldg-chiban.py -- 建物1つ1つに地番を振る（v9.649）
下田さん(2026-11-13)「ピンが正確に立たないのがダメ。建物を押すと点滅して選べて、その建物に地番を振ってくれたら正確になる」

材料:
  建物 = 国土地理院ベクトルタイル experimental_bvmap z16 の building（アプリも同じタイルを読む）
  地番 = 法務省 登記所備付地図データ（jiage-chiban/data/moj/<市区町村コード>.geojson）
やり方: 建物の重心が入っている筆の地番をその建物に振る。アプリとは「z16タイル番号＋タイル内の建物の順番」で突き合わせる。
出力: areas/chiban/<z13のx>_<y>.json  {"o":[町名...], "q":[町の当たり率%(-1=不明)...], "t":{"x_y":[[建物の順番, 町名の番号, "地番"], ...]}}
答え合わせ: 謄本で地番が分かっているピン → 一番近い建物 → 振った地番 と比べる（--eval ピン.json）
使い方: python scripts/build-bldg-chiban.py <z16タイルの置き場> [--eval jiage_all.json]
"""
import glob, json, math, os, re, sys, time, unicodedata, urllib.request, collections
from concurrent.futures import ThreadPoolExecutor
import mapbox_vector_tile as M
from shapely.geometry import shape, Point, Polygon
from shapely import STRtree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOJ = r"C:\Users\st106\jiage-chiban\data\moj"
CACHE = sys.argv[1]
OUT = os.path.join(ROOT, "areas", "chiban")
Z = 16; N = 2 ** Z


def tky2jgd(lat, lon):
    return (lat - 0.00010695 * lat + 0.000017464 * lon + 0.0046017, lon - 0.000046038 * lat - 0.000083043 * lon + 0.010040)


def tileof(lat, lon):
    return int((lon + 180) / 360 * N), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * N)


def px2ll(tx, ty, px, py, ext):
    x = (tx + px / ext) / N; y = (ty + py / ext) / N
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y)))), x * 360 - 180


def ring_centroid(r):
    a = cx = cy = 0.0
    for i in range(len(r) - 1):
        x0, y0 = r[i]; x1, y1 = r[i + 1]
        f = x0 * y1 - x1 * y0; a += f; cx += (x0 + x1) * f; cy += (y0 + y1) * f
    if abs(a) < 1e-9:
        xs = [p[0] for p in r]; ys = [p[1] for p in r]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    return cx / (3 * a), cy / (3 * a)


def buildings(t):
    """z16タイルの建物を [(順番, 重心lat, lng)] で返す。順番＝building層の地物の並び（アプリと同じ）"""
    fn = os.path.join(CACHE, f"{t[0]}_{t[1]}.pbf")
    if not os.path.exists(fn) or os.path.getsize(fn) == 0: return []
    d = M.decode(open(fn, "rb").read(), default_options={"y_coord_down": True})
    b = d.get("building")
    if not b: return []
    ext = b.get("extent", 4096); out = []
    for i, f in enumerate(b["features"]):
        g = f["geometry"]
        if g["type"] == "Polygon": ring = g["coordinates"][0]
        elif g["type"] == "MultiPolygon": ring = max((p[0] for p in g["coordinates"]), key=len)
        else: continue
        if len(ring) < 4: continue
        cx, cy = ring_centroid(ring)
        if not (0 <= cx < ext and 0 <= cy < ext): continue   # 隣のタイルの「のりしろ」部分は隣で数える
        la, lo = px2ll(t[0], t[1], cx, cy, ext)
        out.append((i, la, lo, [px2ll(t[0], t[1], x, y, ext)[::-1] for x, y in ring]))
    return out


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


def nz(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"[ー－−‐―–—]", "-", s).replace(" ", "")


def main():
    os.makedirs(CACHE, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    codes = sorted(os.path.basename(f)[:5] for f in glob.glob(os.path.join(MOJ, "*.geojson")) if os.path.getsize(f) > 10000)
    city_tiles = {}
    for code in codes:
        fn = os.path.join(ROOT, "areas", code + ".geojson")
        if not os.path.exists(fn): continue
        ts = set()
        for ft in json.load(open(fn, encoding="utf-8"))["features"]:
            hc = ft["properties"].get("hc") or []
            for i in range(2, len(hc), 2):
                r, c = hc[0] + hc[i], hc[1] + hc[i + 1]
                for fr, fc in ((.05, .05), (.95, .05), (.05, .95), (.95, .95)):
                    la, lo = tky2jgd((r + fr) / 1200, 100 + (c + fc) / 800); ts.add(tileof(la, lo))
        city_tiles[code] = ts
    alltiles = set().union(*city_tiles.values())
    todo = [t for t in alltiles if not os.path.exists(os.path.join(CACHE, f"{t[0]}_{t[1]}.pbf"))]
    print("市町村", len(city_tiles), "タイル", len(alltiles), "取得", len(todo), flush=True)
    n = 0
    with ThreadPoolExecutor(8) as ex:
        for _ in ex.map(fetch, todo):
            n += 1
            if n % 1000 == 0: print("取得", n, flush=True)

    oaza = []; oidx = {}
    tiles_out = collections.defaultdict(dict)   # z13 -> {"x_y": [[i,o,cb]]}
    bl_index = {}   # 答え合わせ用 (tile) -> [(i,lat,lng)]
    assigned = {}   # (tile,i) -> (町名, 地番)
    for code in codes:
        if code not in city_tiles: continue
        d = json.load(open(os.path.join(MOJ, code + ".geojson"), encoding="utf-8"))
        geoms, metas = [], []
        for ft in d["features"]:
            try:
                g = shape(ft["geometry"])
                if not g.is_empty and g.bounds[0] > 120: geoms.append(g); metas.append(ft["properties"])
            except Exception: pass
        del d
        if not geoms: print(code, "地図なし", flush=True); continue
        tree = STRtree(geoms); cnt = 0
        for t in city_tiles[code]:
            bs = bl_index.get(t)
            if bs is None: bs = bl_index[t] = buildings(t)
            for i, la, lo, rg in bs:
                if (t, i) in assigned: continue
                p = Point(lo, la)
                hit = [k for k in tree.query(p) if geoms[k].contains(p)]
                if not hit: continue
                m = metas[hit[0]]
                town = nz((m.get("市区町村名") or "") + (m.get("大字名") or "") + (m.get("丁目名") or ""))
                cb = nz(m.get("地番") or "")
                if not cb: continue
                assigned[(t, i)] = (town, cb); cnt += 1
        print(code, metas[0].get("市区町村名"), "建物に地番", cnt, flush=True)
        del geoms, metas, tree

    for (t, i), (town, cb) in assigned.items():
        if town not in oidx: oidx[town] = len(oaza); oaza.append(town)
        k13 = f"{t[0] >> 3}_{t[1] >> 3}"
        tiles_out[k13].setdefault(f"{t[0]}_{t[1]}", []).append([i, oidx[town], cb])
    # 町ごとの当たり率(%) = 謄本で地番が分かっているピンで答え合わせ。町で5件未満なら市の当たり率(10件以上)、それも無ければ -1(不明)
    #  ※「建物が1つの筆に収まっているか」では、ずれている町を見分けられなかった(2026-11-14)
    qual = {}
    if "--eval" in sys.argv:
        items = json.load(open(sys.argv[sys.argv.index("--eval") + 1], encoding="utf-8"))
        res = collections.Counter(); bytown = collections.defaultdict(collections.Counter); bycity = collections.defaultdict(collections.Counter)
        def city_of(tw):
            m = re.match(r"(.+?郡.+?[町村]|さいたま市.+?区|.+?市|.+?町)", tw); return m.group(1) if m else tw
        for it in items:
            if not it.get("tohonPdf") or not it.get("address") or "地番地図" in str(it.get("addressSource") or ""): continue
            a2 = re.sub(r"番地?の?", "-", nz(it["address"]).replace("埼玉県", "")).rstrip("-")
            mm = re.search(r"(\d+(?:-\d+)*)$", a2)
            if not mm: continue
            truth = mm.group(1); la, lo = it["lat"], it["lng"]
            tx, ty = tileof(la, lo); best = None
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    t = (tx + dx, ty + dy)
                    for i, bla, blo, _r in bl_index.get(t, []):
                        dd = math.hypot((bla - la) * 111000, (blo - lo) * 90000)
                        if best is None or dd < best[0]: best = (dd, t, i)
            if best is None or best[0] > 30 or (best[1], best[2]) not in assigned: continue
            town, cb = assigned[(best[1], best[2])]
            k = "一致" if cb == truth else "ちがう"
            res[k] += 1; bytown[town][k] += 1; bycity[city_of(town)][k] += 1
        print("答え合わせ(一番近い建物の地番)", dict(res), "当たり%d%%" % round(100 * res["一致"] / max(1, sum(res.values()))))
        pct = lambda v: round(100 * v["一致"] / sum(v.values()))
        for tw in {x[0] for x in assigned.values()}:
            v = bytown.get(tw); cv = bycity.get(city_of(tw))
            qual[tw] = pct(v) if v and sum(v.values()) >= 5 else (pct(cv) if cv and sum(cv.values()) >= 10 else -1)
        for c, v in sorted(bycity.items(), key=lambda x: -sum(x[1].values())):
            print(" ", c, dict(v), "%d%%" % pct(v))
        low = sorted(tw for tw, q in qual.items() if 0 <= q < 60)
        print("当たりが低い町(自動で入れない)", len(low), low[:40])
    # z13 ファイルごとに町名表を小さくする
    total = 0
    for k13, tt in tiles_out.items():
        used = sorted({x[1] for v in tt.values() for x in v}); remap = {o: j for j, o in enumerate(used)}
        body = {"o": [oaza[o] for o in used], "q": [qual.get(oaza[o], -1) for o in used], "t": {k: sorted([[x[0], remap[x[1]], x[2]] for x in v]) for k, v in tt.items()}}
        s2 = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        open(os.path.join(OUT, k13 + ".json"), "w", encoding="utf-8").write(s2); total += len(s2.encode())
    print("建物に地番", len(assigned), "ファイル", len(tiles_out), "合計", round(total / 1e6, 1), "MB", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
