"""探索候補エリア用の区画データ（町丁・字）を作る。事前に1回だけ動かすスクリプト。

出力：
  areas/index.json        … 市区町村の一覧（コード・名前・区画数・範囲）
  areas/<市区町村コード>.geojson … その市区町村の区画（形は簡略化済み）

区画ごとの属性：
  k   区画ID（e-Stat KEY_CODE）       c  市区町村コード（5桁）   cn 市区町村名
  n   町丁・字名                       p  人口    h 世帯数
  o   高齢化率（65歳以上 ÷ 年齢が分かる人口。0〜1、分からなければ null）
  d   一戸建て割合（一戸建 ÷ 主世帯数。0〜1、分からなければ null）
  lp  番号を出す位置 [lat, lng]（区画の内側に必ず入る点）

出典（すべて e-Stat 統計GIS・令和2年国勢調査 小地域（町丁・字等別）・埼玉県）：
  境界   … dlserveyId=A002005212020 （世界測地系・緯度経度・Shape）
  T001082 … 男女，年齢（5歳階級及び3区分）別人口
  T001086 … 住宅の建て方別主世帯数
使い方：
  pip install pyshp shapely
  python scripts/build-area-geojson.py            # ダウンロードから全部
  python scripts/build-area-geojson.py --tol 0.00008  # 簡略化の強さを変える（度。0.0001≒10m）
"""
import argparse, csv, io, json, os, sys, tempfile, urllib.request, zipfile
from collections import defaultdict

import shapefile  # pyshp
from shapely.geometry import shape, mapping, MultiPolygon, Polygon
from shapely.ops import unary_union

PREF = "11"
URL_BOUNDARY = ("https://www.e-stat.go.jp/gis/statmap-search/data?dlserveyId=A002005212020"
                f"&code={PREF}&coordSys=1&format=shape&downloadType=5&datum=2000")
URL_TABLE = "https://www.e-stat.go.jp/gis/statmap-search/data?statsId={sid}&code=" + PREF + "&downloadType=2"
WATER_HCODE = 8154  # 水面調査区（川・湖）は区画にしない


def fetch(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    print("ダウンロード:", url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r, open(path, "wb") as f:
        f.write(r.read())
    return path


def read_table(zpath):
    """e-Stat の小地域集計 txt（cp932・2行目が項目名）→ {KEY_CODE: row}。秘匿先は合算先の値を使う。"""
    with zipfile.ZipFile(zpath) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".txt")][0]
        text = z.read(name).decode("cp932")
    rows = list(csv.reader(io.StringIO(text)))
    head, data = rows[0], rows[2:]
    out = {}
    for r in data:
        if not r or not r[0]:
            continue
        out[r[0]] = dict(zip(head, r))
    return out


def num(v):
    if v in (None, "", "-"):
        return 0
    if v in ("X", "*"):
        return None
    try:
        return int(v)
    except ValueError:
        return None


def resolve(tab, key):
    """秘匿（HTKSYORI=2）の区画は、合算先（同じ市区町村内の HTKSAKI）の行を返す。"""
    r = tab.get(key)
    if r and r.get("HTKSYORI") == "2" and r.get("HTKSAKI"):
        alt = key[:5] + r["HTKSAKI"].split(";")[0]
        for cand in (alt, alt.ljust(len(key), "0")):
            if cand in tab:
                return tab[cand]
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=0.00007, help="簡略化の許容誤差（度）")
    ap.add_argument("--work", default=os.path.join(tempfile.gettempdir(), "hikari-area-build"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "areas"))
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    os.makedirs(a.out, exist_ok=True)

    bz = fetch(URL_BOUNDARY, os.path.join(a.work, "boundary.zip"))
    t_age = read_table(fetch(URL_TABLE.format(sid="T001082"), os.path.join(a.work, "T001082.zip")))
    t_house = read_table(fetch(URL_TABLE.format(sid="T001086"), os.path.join(a.work, "T001086.zip")))

    with zipfile.ZipFile(bz) as z:
        z.extractall(a.work)
    shp = [f for f in os.listdir(a.work) if f.lower().endswith(".shp")][0]
    rd = shapefile.Reader(os.path.join(a.work, shp), encoding="cp932")

    # 同じ KEY_CODE の多角形（飛び地）をまとめる
    parts = defaultdict(list)
    meta = {}
    for sr in rd.iterShapeRecords():
        d = sr.record.as_dict()
        if d.get("HCODE") == WATER_HCODE:
            continue
        geom = shape(sr.shape.__geo_interface__)
        if geom.is_empty:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
        k = d["KEY_CODE"]
        parts[k].append(geom)
        m = meta.setdefault(k, {"c": d["PREF"] + d["CITY"], "cn": d["CITY_NAME"], "n": d["S_NAME"] or "", "p": 0, "h": 0})
        m["p"] += d.get("JINKO") or 0
        m["h"] += d.get("SETAI") or 0

    # 同じ名前の区画が市内に複数ある（大字が字ごとに分かれている）時は ①② を付けて区別する
    name_count = defaultdict(int)
    for k, m in meta.items():
        name_count[(m["c"], m["n"])] += 1
    name_seq = defaultdict(int)
    circ = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

    by_city = defaultdict(list)
    for k in sorted(meta):
        m = meta[k]
        g = unary_union(parts[k]).simplify(a.tol, preserve_topology=True)
        if g.is_empty:
            continue
        if isinstance(g, Polygon):
            g = MultiPolygon([g])
        elif not isinstance(g, MultiPolygon):
            polys = [x for x in getattr(g, "geoms", []) if isinstance(x, Polygon)]
            if not polys:
                continue
            g = MultiPolygon(polys)
        # ごく小さい飛び地（簡略化で潰れた欠片）を落とす
        big = [p for p in g.geoms if p.area > (a.tol * a.tol * 4)]
        if big:
            g = MultiPolygon(big)
        name = m["n"] or "（名称なし）"
        if name_count[(m["c"], m["n"])] > 1:
            name_seq[(m["c"], m["n"])] += 1
            i = name_seq[(m["c"], m["n"])]
            name = name + (circ[i - 1] if i <= len(circ) else f"({i})")
        ra = resolve(t_age, k)
        o = None
        if ra:
            y = num(ra.get("T001082017")); w = num(ra.get("T001082018")); s = num(ra.get("T001082019"))
            if None not in (y, w, s) and (y + w + s) > 0:
                o = round(s / (y + w + s), 3)
        rh = resolve(t_house, k)
        dt = None
        if rh:
            tot = num(rh.get("T001086001")); one = num(rh.get("T001086002"))
            if tot and one is not None:
                dt = round(one / tot, 3)
        lp = g.representative_point() if len(g.geoms) == 1 else max(g.geoms, key=lambda x: x.area).representative_point()

        def rnd(coords):
            return [[round(x, 5), round(y, 5)] for x, y in coords]
        coords = []
        for poly in g.geoms:
            rings = [rnd(poly.exterior.coords)] + [rnd(r.coords) for r in poly.interiors]
            coords.append(rings)
        by_city[m["c"]].append({
            "type": "Feature",
            "properties": {"k": k, "c": m["c"], "cn": m["cn"], "n": name, "p": m["p"], "h": m["h"],
                           "o": o, "d": dt, "lp": [round(lp.y, 5), round(lp.x, 5)]},
            "geometry": {"type": "MultiPolygon", "coordinates": coords},
        })

    index = []
    total = 0
    biggest = (0, "")
    for c, feats in sorted(by_city.items()):
        path = os.path.join(a.out, f"{c}.geojson")
        body = json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":"))
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        size = len(body.encode("utf-8"))
        total += size
        if size > biggest[0]:
            biggest = (size, feats[0]["properties"]["cn"])
        xs = [pt[0] for ft in feats for poly in ft["geometry"]["coordinates"] for pt in poly[0]]
        ys = [pt[1] for ft in feats for poly in ft["geometry"]["coordinates"] for pt in poly[0]]
        index.append({"c": c, "n": feats[0]["properties"]["cn"], "count": len(feats),
                      "bbox": [round(min(ys), 4), round(min(xs), 4), round(max(ys), 4), round(max(xs), 4)]})
    with open(os.path.join(a.out, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"source": "e-Stat 令和2年国勢調査 小地域（町丁・字等別）", "cities": index}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"市区町村 {len(index)} / 区画 {sum(x['count'] for x in index)} / 合計 {total/1024/1024:.2f}MB / 最大 {biggest[1]} {biggest[0]/1024:.0f}KB")


if __name__ == "__main__":
    sys.exit(main())
