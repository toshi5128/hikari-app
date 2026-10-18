"""探索候補エリアの区画データ（areas/<市区町村コード>.geojson）に「古い団地らしさ」用の数字を足す。
build-area-geojson.py で区画を作った後に1回だけ動かす（区画の形・既存の数字には触らない）。

足す属性：
  s   5年前も今と同じ家に住んでいた人の割合（現住所 ÷ (現住所＋移動あり)。0〜1、分からなければ null）
      → 長く住み続けている人が多い＝昔に分譲されて世代が入れ替わっていない町の目印
  pk  区画の中で一番人が多い250mマスの人口（田畑の中にかたまった団地を「まばら」と誤判定しないため）
  po  そのマスの高齢化率   ps そのマスの「5年前も同じ家」の割合（大字の中の団地部分だけの数字）
  u   用途地域の外（≒市街化調整区域）にある面積の割合（0〜1。用途地域データが無い市町村は null）

出典：
  e-Stat 統計GIS 令和2年国勢調査 4次メッシュ(250m) 移動人口 T001187 / T001199・年齢 T001175 / T001196
        （同じ表が2組ある。区画の人口と一番よく合う方を自動で選ぶ）
  youto-area.json（国土数値情報 A29 用途地域。tools/make-youto.py で作成済みの物）
使い方：
  pip install shapely
  python scripts/add-koho-oldtown.py
"""
import csv, io, json, os, sys, tempfile, urllib.request, zipfile, glob
from collections import defaultdict

from shapely.geometry import shape, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
URL_TABLE = "https://www.e-stat.go.jp/gis/statmap-search/data?statsId={sid}&code=11&downloadType=2"
WORK = os.path.join(tempfile.gettempdir(), "hikari-koho")


def fetch(sid):
    os.makedirs(WORK, exist_ok=True)
    path = os.path.join(WORK, sid + ".zip")
    if not (os.path.exists(path) and os.path.getsize(path) > 1000):
        print("ダウンロード:", sid)
        req = urllib.request.Request(URL_TABLE.format(sid=sid), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180) as r, open(path, "wb") as f:
            f.write(r.read())
    with zipfile.ZipFile(path) as z:
        text = z.read([n for n in z.namelist() if n.lower().endswith(".txt")][0]).decode("cp932")
    rows = list(csv.reader(io.StringIO(text)))
    return rows[0], rows[2:]


def mesh_center(code):
    """4次メッシュ(10桁)の中心 [lat, lng]"""
    lat = int(code[0:2]) / 1.5 + int(code[4]) * (5 / 60) + int(code[6]) * (30 / 3600)
    lng = int(code[2:4]) + 100 + int(code[5]) * (7.5 / 60) + int(code[7]) * (45 / 3600)
    dl, dg = 15 / 3600, 22.5 / 3600
    for ch in code[8:10]:
        q = int(ch) - 1
        if q >= 2:
            lat += dl
        if q % 2 == 1:
            lng += dg
        dl, dg = dl / 2, dg / 2
    return lat + dl, lng + dg


def load_age(sid):
    """250mマスごとの (65歳以上, 年齢が分かる人口)"""
    head, data = fetch(sid)
    col = {h: i for i, h in enumerate(head)}
    out = {}
    for r in data:
        if not r or len(r[0]) != 10:
            continue
        v = [r[col[f"{sid}{i:03d}"]] for i in range(4, 62, 3)]
        if all(x.isdigit() for x in v):
            v = [int(x) for x in v]
            out[r[0]] = (sum(v[13:]), sum(v))
    return out


def load_mesh(sid, age):
    head, data = fetch(sid)
    col = {h: i for i, h in enumerate(head)}
    p0, stay, moved = col[sid + "001"], col[sid + "004"], col[sid + "007"]
    out = []
    for r in data:
        if not r or len(r[0]) != 10:
            continue
        v = [r[p0], r[stay], r[moved]]
        if not all(x.isdigit() for x in v):
            continue  # 秘匿（合算先に入っている）
        out.append((r[0], int(v[0]), int(v[1]), int(v[2])) + age.get(r[0], (0, 0)))
    return out


def youto_union():
    raw = json.load(open(os.path.join(ROOT, "youto-area.json"), encoding="utf-8"))
    sc = raw.get("scale", 100000)
    cities = raw.get("cities", [])
    polys = defaultdict(list)
    for z in raw["z"]:
        rings = []
        for flat in z[4]:
            x = y = 0
            pts = []
            for i in range(0, len(flat) - 1, 2):
                x += flat[i]; y += flat[i + 1]
                pts.append((x / sc, y / sc))
            if len(pts) >= 3:
                rings.append(pts)
        if not rings:
            continue
        g = Polygon(rings[0], rings[1:])
        if not g.is_valid:
            g = g.buffer(0)
        polys[cities[z[3]] if z[3] < len(cities) else ""].append(g)
    return {c: unary_union(g) for c, g in polys.items()}


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "areas", "1*.geojson")))
    fcs = {fn: json.load(open(fn, encoding="utf-8")) for fn in files}
    feats = [(f, shape(f["geometry"])) for fc in fcs.values() for f in fc["features"]]
    tree = STRtree([g for _, g in feats])
    preps = [prep(g) for _, g in feats]

    def assign(meshes):
        acc = defaultdict(lambda: [0, 0, 0, None])   # 人口, 現住所, 移動あり, 一番人の多いマス
        cells = []
        for m in meshes:
            la, lo = mesh_center(m[0])
            c = (la, lo) + m[1:]          # lat, lng, 人口, 現住所, 移動あり, 65歳以上, 年齢が分かる人口
            cells.append(c)
            pt = Point(lo, la)
            for i in tree.query(pt):
                if preps[i].contains(pt):
                    a = acc[i]
                    a[0] += c[2]; a[1] += c[3]; a[2] += c[4]
                    if a[3] is None or c[2] > a[3][2]:
                        a[3] = c
                    break
        return acc, cells

    # 同じ表が2つずつある（T001187+T001175 / T001199+T001196）。区画の人口と合う方を使う
    best = None
    for sid, aid in (("T001187", "T001175"), ("T001199", "T001196")):
        acc, cells = assign(load_mesh(sid, load_age(aid)))
        err = sum(abs(acc[i][0] - f["properties"]["p"]) for i, (f, _) in enumerate(feats) if f["properties"]["p"] > 300)
        print(f"{sid}: 区画人口とのずれ合計 {err:,}")
        if best is None or err < best[0]:
            best = (err, sid, acc, cells)
    _, sid, acc, cells = best
    print("採用:", sid)

    ratio = lambda x, n: round(x / n, 3) if n >= 20 else None
    youto = youto_union()
    n_s = n_u = 0
    for i, (f, g) in enumerate(feats):
        pr = f["properties"]
        a = acc.get(i)
        if not a or a[1] + a[2] < 20:
            # 区画が小さくてマスの中心が入らない時は、番号位置に一番近いマスで代用
            la, lo = pr["lp"]
            near = min(cells, key=lambda c: (c[0] - la) ** 2 + ((c[1] - lo) * 0.81) ** 2)
            a = [near[2], near[3], near[4], near] if (near[0] - la) ** 2 + ((near[1] - lo) * 0.81) ** 2 < 0.003 ** 2 else None
        top = a[3] if a else None
        pr["s"] = ratio(a[1], a[1] + a[2]) if a else None
        pr["pk"] = top[2] if top else 0
        pr["po"] = ratio(top[5], top[6]) if top else None
        pr["ps"] = ratio(top[3], top[3] + top[4]) if top else None
        cn = pr["cn"]
        yu = youto.get(cn, youto.get(cn.split("市")[0] + "市") if "市" in cn else None)
        if yu is not None and g.area > 0:
            pr["u"] = round(max(0.0, 1 - g.intersection(yu).area / g.area), 3)
            n_u += 1
        else:
            pr["u"] = None
        n_s += pr["s"] is not None
    for fn, fc in fcs.items():
        with open(fn, "w", encoding="utf-8") as f:
            f.write(json.dumps(fc, ensure_ascii=False, separators=(",", ":")))
    print(f"区画 {len(feats)} / 5年居住率あり {n_s} / 調整区域割合あり {n_u}")


if __name__ == "__main__":
    sys.exit(main())
