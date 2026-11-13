# -*- coding: utf-8 -*-
"""
build-house-cells.py -- 探索候補の区画を「家が建っている所だけ」塗るためのデータ。v9.640

下田さん(2026-11-13)「区画の中の何も家が建っていない畑まで赤くなっている。家が建っている所だけ赤く囲んでほしい」

国土地理院ベクトルタイル(experimental_bvmap z15 の building)で、100mマス(国交省メッシュと同じ区切り)ごとに
戸建てサイズ(30〜400㎡)の建物を数え、MIN 軒以上のマスを「家のあるマス」として町丁(areas/*.geojson)に振り分け、
properties.hc = [基準行, 基準列, 行差, 列差, 行差, 列差, ...] で持たせる（アプリはこのマスだけを塗る）。

使い方: python scripts/build-house-cells.py <タイルの置き場フォルダ>
"""
import glob, json, math, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
import mapbox_vector_tile as M

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AREAS = os.path.join(ROOT, "areas")
CACHE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_bv15")
MIN = 4          # 100mマスにこれ以上の家があれば「家のあるマス」
Z = 15; N = 2 ** Z


def tky2jgd(lat, lon):
    return (lat - 0.00010695 * lat + 0.000017464 * lon + 0.0046017, lon - 0.000046038 * lat - 0.000083043 * lon + 0.010040)


def jgd2tky(lat, lon):
    a = tky2jgd(lat, lon); return (lat - (a[0] - lat), lon - (a[1] - lon))


def cellof(lat, lng):
    t = jgd2tky(lat, lng); return (int(math.floor(t[0] * 1200)), int(math.floor((t[1] - 100) * 800)))


def tileof(lat, lon):
    return int((lon + 180) / 360 * N), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * N)


def t2ll(x, y):
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / N)))), x / N * 360 - 180


def inside(x, y, ring):
    c = False
    for i in range(len(ring)):
        x1, y1 = ring[i]; x2, y2 = ring[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def contains(polys, x, y):
    for p in polys:
        if inside(x, y, p[0]) and not any(inside(x, y, h) for h in p[1:]):
            return True
    return False


def fetch(t):
    fn = os.path.join(CACHE, f"{t[0]}_{t[1]}.pbf")
    if os.path.exists(fn):
        return
    for _ in range(4):
        try:
            b = urllib.request.urlopen(f"https://cyberjapandata.gsi.go.jp/xyz/experimental_bvmap/{Z}/{t[0]}/{t[1]}.pbf", timeout=40).read()
            open(fn, "wb").write(b); return
        except urllib.error.HTTPError as e:
            if e.code == 404:
                open(fn, "wb").write(b""); return
            time.sleep(2)
        except Exception:
            time.sleep(2)


def main():
    os.makedirs(CACHE, exist_ok=True)
    files = sorted(glob.glob(os.path.join(AREAS, "1*.geojson")))
    tiles = set()
    for fn in files:
        for ft in json.load(open(fn, encoding="utf-8"))["features"]:
            g = ft["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            xs = [p[0] for poly in polys for p in poly[0]]; ys = [p[1] for poly in polys for p in poly[0]]
            x0, y1 = tileof(min(ys), min(xs)); x1, y0 = tileof(max(ys), max(xs))
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    tiles.add((x, y))
    print("tiles", len(tiles), flush=True)
    n = 0
    with ThreadPoolExecutor(8) as ex:
        for _ in ex.map(fetch, sorted(tiles)):
            n += 1
            if n % 500 == 0:
                print("fetched", n, flush=True)
    cnt = {}
    for t in tiles:
        fn = os.path.join(CACHE, f"{t[0]}_{t[1]}.pbf")
        if not os.path.exists(fn) or os.path.getsize(fn) == 0:
            continue
        L = M.decode(open(fn, "rb").read()).get("building")
        if not L:
            continue
        ext = L.get("extent", 4096)
        la0, lo0 = t2ll(t[0], t[1]); la1, lo1 = t2ll(t[0] + 1, t[1] + 1)
        mx = (lo1 - lo0) * 91000 / ext; my = (la0 - la1) * 111000 / ext
        for f in L["features"]:
            g = f["geometry"]
            ring = g["coordinates"][0] if g["type"] == "Polygon" else (g["coordinates"][0][0] if g["type"] == "MultiPolygon" else None)
            if not ring:
                continue
            A = 0
            for i in range(len(ring)):
                A += ring[i - 1][0] * ring[i][1] - ring[i][0] * ring[i - 1][1]
            area = abs(A) / 2 * mx * my
            if not (30 <= area <= 400):
                continue
            cx = sum(p[0] for p in ring) / len(ring); cy = sum(p[1] for p in ring) / len(ring)
            k = cellof(la1 + (la0 - la1) * cy / ext, lo0 + (lo1 - lo0) * cx / ext)
            cnt[k] = cnt.get(k, 0) + 1
    house = [k for k, v in cnt.items() if v >= MIN]
    print("house cells", len(house), flush=True)
    grid = {}
    for k in house:
        la, lo = tky2jgd((k[0] + .5) / 1200, 100 + (k[1] + .5) / 800)
        grid.setdefault((int(la * 100), int(lo * 100)), []).append((k, la, lo))
    used = set(); total = 0
    for fn in files:
        fc = json.load(open(fn, encoding="utf-8"))
        for ft in fc["features"]:
            g = ft["geometry"]; polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            xs = [p[0] for poly in polys for p in poly[0]]; ys = [p[1] for poly in polys for p in poly[0]]
            w, s, e, nn = min(xs), min(ys), max(xs), max(ys)
            mine = []
            for gy in range(int(s * 100), int(nn * 100) + 1):
                for gx in range(int(w * 100), int(e * 100) + 1):
                    for k, la, lo in grid.get((gy, gx), ()):
                        if k in used or not (s <= la <= nn and w <= lo <= e):
                            continue
                        if contains(polys, lo, la):
                            used.add(k); mine.append(k)
            mine.sort()
            if mine:
                r0, c0 = mine[0]
                flat = [r0, c0]
                for k in mine:
                    flat += [k[0] - r0, k[1] - c0]
                ft["properties"]["hc"] = flat
            else:
                ft["properties"]["hc"] = []
            total += len(mine)
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
    print("assigned", total, "DONE", flush=True)


if __name__ == "__main__":
    main()
