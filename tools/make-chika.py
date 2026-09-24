# 基準地価レイヤー用データ（chika-points.json）を作る
#
# 国土数値情報（国土交通省）の
#   L01 地価公示（毎年1月1日時点・3月発表）
#   L02 地価調査（毎年7月1日時点・9月発表 ＝ 都道府県の「基準地価」）
# の埼玉県分をダウンロードして、地図で使う項目だけに絞った軽いJSONにする。
#
# 使い方（リポジトリ直下で）:
#   python tools/make-chika.py            ← 既定の年（下の YEAR）
#   python tools/make-chika.py 27         ← 令和9年版(2027) が出たら
#
# 出典表記: 「国土数値情報（地価公示データ・都道府県地価調査データ）」（国土交通省）を加工して作成

import io
import json
import sys
import urllib.request
import zipfile

PREF = "11"   # 埼玉
YEAR = sys.argv[1] if len(sys.argv) > 1 else "26"   # 2026年 = 26
OUT = "chika-points.json"
BASE = "https://nlftp.mlit.go.jp/ksj/gml/data"


def fetch_geojson(kind):
    url = f"{BASE}/{kind}/{kind}-{YEAR}/{kind}-{YEAR}_{PREF}_GML.zip"
    print("download", url)
    b = urllib.request.urlopen(url, timeout=180).read()
    z = zipfile.ZipFile(io.BytesIO(b))
    name = next(n for n in z.namelist() if n.endswith(".geojson"))
    return json.loads(z.read(name).decode("utf-8"))["features"]


def clean_addr(s):
    s = (s or "").replace("埼玉県　", "").replace("埼玉県", "").strip()
    return "" if s == "_" else s


def val(s):
    return "" if s in (None, "_") else s


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


# 項目番号（国土数値情報の仕様書どおり）
#   公示 L01: 007年 008価格 009前年比 024地名 002用途 003番号 025所在 027地積 028利用現況
#             040前面道路 042道路幅 047周辺 048駅 050駅距離 051用途地域 053区域 057建ぺい 058容積
#             105=今年 100=5年前
#   調査 L02: 005年 006価格 007前年比 021地名 003用途 004番号 022所在 024地積 025利用現況
#             037前面道路 039道路幅 044周辺 045駅 046駅距離 047用途地域 049区域 051建ぺい 052容積
#             099=今年 094=5年前
SPEC = {
    "L01": dict(k=0, year="007", price="008", chg="009", name="024", cat="002", no="003",
                addr="025", area="027", use="028", road="040", roadw="042", env="047",
                sta="048", dist="050", zone="051", ku="053", bcr="057", far="058", p5="100"),
    "L02": dict(k=1, year="005", price="006", chg="007", name="021", cat="003", no="004",
                addr="022", area="024", use="025", road="037", roadw="039", env="044",
                sta="045", dist="046", zone="047", ku="049", bcr="051", far="052", p5="094"),
}

pts = []
years = {}
for kind, sp in SPEC.items():
    for f in fetch_geojson(kind):
        p = f["properties"]
        g = lambda key: p.get(f"{kind}_{sp[key]}")
        lng, lat = f["geometry"]["coordinates"]
        price = int(g("price") or 0)
        if price <= 0:
            continue
        years[sp["k"]] = int(g("year"))
        p5 = int(num(g("p5")))
        pts.append([
            sp["k"],                         # 0 種類 0=公示 1=調査
            round(lat, 5), round(lng, 5),    # 1,2
            price,                           # 3 円/㎡
            num(g("chg")),                   # 4 前年比 %
            p5 if p5 > 0 else 0,             # 5 5年前の価格（無ければ0）
            val(g("name")),                  # 6 地名（例: さいたま西）
            int(g("cat") or 0),              # 7 用途 0住宅 3準住 5商業 7準工 9工業 10/13調区 20林地
            int(g("no") or 0),               # 8 番号
            clean_addr(g("addr")),           # 9 所在（地番）
            int(num(g("area"))),             # 10 地積 ㎡
            val(g("use")).replace("@", "・"),  # 11 利用現況
            val(g("env")),                   # 12 周辺の状況
            val(g("sta")),                   # 13 最寄駅
            int(num(g("dist"))),             # 14 駅距離 m
            val(g("zone")),                  # 15 用途地域
            val(g("ku")),                    # 16 市街化／調区 など
            int(num(g("bcr"))), int(num(g("far"))),  # 17,18 建ぺい/容積
            val(g("road")), num(g("roadw")),  # 19,20 前面道路・幅員
        ])

# 繰り返し出てくる文字（地名・周辺・駅・用途地域など）は一覧 s に1回だけ置き、番号で引く＝軽くする
DICT_COLS = (6, 11, 12, 13, 15, 16, 19)
strs, sidx = [], {}
for row in pts:
    for c in DICT_COLS:
        v = row[c]
        if v not in sidx:
            sidx[v] = len(strs)
            strs.append(v)
        row[c] = sidx[v]
    row[4] = round(row[4], 1)
    row[20] = round(row[20], 1)

out = {
    "src": "国土数値情報（地価公示・都道府県地価調査）国土交通省 を加工",
    "years": [years.get(0), years.get(1)],
    "dict": list(DICT_COLS),
    "s": strs,
    "pts": pts,
}
with open(OUT, "w", encoding="utf-8") as fp:
    json.dump(out, fp, ensure_ascii=False, separators=(",", ":"))
print(f"{OUT}: {len(pts)} 地点  公示{years.get(0)} / 調査{years.get(1)}")
