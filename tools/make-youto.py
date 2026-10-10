# 用途地域レイヤー用データ（youto-area.json）を作る
#
# 国土数値情報（国土交通省）の A29 用途地域 の埼玉県分をダウンロードして、
# 地上げの担当エリアの市町だけを切り出し、形を少し間引いて軽いJSONにする。
#
# 使い方（リポジトリ直下で）:
#   python tools/make-youto.py            ← 既定の年（下の YEAR）
#   python tools/make-youto.py 23         ← 新しい年度版が出たら
#
# 必要: pip install shapely
# 出典表記: 「国土数値情報（用途地域データ）」（国土交通省）を加工して作成

import io
import json
import sys
import urllib.request
import zipfile

from shapely.geometry import shape, Polygon, MultiPolygon

PREF = "11"   # 埼玉
YEAR = sys.argv[1] if len(sys.argv) > 1 else "19"   # 令和元年度 = 19
OUT = "youto-area.json"
URL = f"https://nlftp.mlit.go.jp/ksj/gml/data/A29/A29-{YEAR}/A29-{YEAR}_{PREF}_GML.zip"

# 担当エリア（index.html の JIAGE_AREAS）の市町コード
#   小川町(11343)は国のデータに用途地域が入っていないので出ない
CITIES = {
    "11202": "熊谷市", "11206": "行田市", "11207": "秩父市", "11211": "本庄市",
    "11212": "東松山市", "11218": "深谷市", "11343": "小川町", "11385": "上里町",
}
TOL = 0.00002   # 間引きの細かさ（度）≒ 2m。これ以下のでこぼこは省く
SCALE = 100000  # 座標は 1/10万度（≒1m）単位の整数にして、前の点との差だけ持つ


def enc_ring(coords):
    out, px, py = [], 0, 0
    for x, y in coords[:-1]:   # 最後の点は最初と同じなので省く
        ix, iy = round(x * SCALE), round(y * SCALE)
        out += [ix - px, iy - py]
        px, py = ix, iy
    return out


print("download", URL)
b = urllib.request.urlopen(URL, timeout=300).read()
z = zipfile.ZipFile(io.BytesIO(b))
city_list = list(CITIES.values())
zones = []
for n in z.namelist():
    code = n[-13:-8]
    if not n.endswith(".geojson") or code not in CITIES:
        continue
    feats = json.loads(z.read(n).decode("utf-8"))["features"]
    for f in feats:
        p = f["properties"]
        g = shape(f["geometry"]).simplify(TOL, preserve_topology=True)
        polys = [g] if isinstance(g, Polygon) else list(g.geoms) if isinstance(g, MultiPolygon) else []
        for pg in polys:
            if pg.is_empty:
                continue
            rings = [enc_ring(list(pg.exterior.coords))] + [enc_ring(list(r.coords)) for r in pg.interiors]
            zones.append([
                int(p["A29_004"] or 0),            # 0 用途地域の番号 1〜13（21=田園住居）
                int(p["A29_006"] or 0),            # 1 建ぺい率 %
                int(p["A29_007"] or 0),            # 2 容積率 %
                city_list.index(CITIES[code]),     # 3 市町
                rings,                             # 4 外周＋穴
            ])
    print(CITIES[code], len(feats))

out = {
    "src": "国土数値情報（用途地域）国土交通省 を加工",
    "year": 2000 + int(YEAR),
    "cities": city_list,
    "scale": SCALE,
    "z": zones,
}
with open(OUT, "w", encoding="utf-8") as fp:
    json.dump(out, fp, ensure_ascii=False, separators=(",", ":"))
print(f"{OUT}: {len(zones)} 面")
