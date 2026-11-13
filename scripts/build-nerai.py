# -*- coding: utf-8 -*-
"""
build-nerai.py -- 🏆 狙い目ランキング（埼玉県全域）のデータを作る。v9.637

下田さん(2026-11-13)「昭和50年代〜平成5年くらいの物件が大好物。そういう家が固まっているエリアを
  優先して空き家を見つけたい。埼玉県全域で分かるようにしてほしい」

元データ:
  takuchi-nendai-2.json … 国交省 土地利用細分メッシュ(100m)を年次で引き算した「田畑・山林→戸建て住宅地」になったマス
    年代 0 = 1976→1987（昭和51〜62） / 1 = 1987→1991（昭和62〜平成3） / 2 = 1991→1997（平成3〜9）
  areas/<市区町村コード>.geojson … e-Stat 令和2年国勢調査の町丁・字の区画

やること:
  1) マスの中心がどの町丁に入るかを調べ、町丁ごとに
       t  = 昭和51〜平成3 に住宅地になった広さ(ha)   ← 一番の狙い
       t9 = 平成3〜9 に住宅地になった広さ(ha)        ← 平成5年ごろまでを含むので準狙い
     を areas/*.geojson の properties に書き足す（探索候補の「おすすめ度」で使う）
  2) areas/nerai.json … 県全域で t+t9 が 2ha 以上の町丁の一覧（ランキング画面用）
       マスの位置(行・列)も持たせ、アプリ側で「もう行ったか」をピン・探索ルートから数える

実績(2026-11-13 集計): 仕入7件は全部この年代の住宅地(と100m以内)。それ以外の場所 1,266ピンからは0件。
  歩いた1haあたり空き家ピン約0.73件・回っている1時間あたり約14件（場所による差はほぼ無し）。

使い方:  python scripts/build-nerai.py   （takuchi / areas を作り直したら再実行）
"""
import glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AREAS = os.path.join(ROOT, "areas")


def tky2jgd(lat, lon):
    return (lat - 0.00010695 * lat + 0.000017464 * lon + 0.0046017,
            lon - 0.000046038 * lat - 0.000083043 * lon + 0.010040)


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


def main():
    tk = json.load(open(os.path.join(ROOT, "takuchi-nendai-2.json"), encoding="utf-8"))
    cells = []                                       # (row, col, era, lat, lng)
    for rec in tk["clusters"]:
        for o in rec[3]:
            r, c = rec[1] + o[0], rec[2] + o[1]
            la, lo = tky2jgd((r + .5) / 1200, 100 + (c + .5) / 800)
            cells.append((r, c, o[2] if len(o) > 2 else 0, la, lo))
    # 0.01度の格子で振り分け（内外判定の足切り）
    grid = {}
    for cl in cells:
        grid.setdefault((int(cl[3] * 100), int(cl[4] * 100)), []).append(cl)
    used = set()
    out = []
    for fn in sorted(glob.glob(os.path.join(AREAS, "1*.geojson"))):
        fc = json.load(open(fn, encoding="utf-8"))
        for ft in fc["features"]:
            g = ft["geometry"]
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            xs = [p[0] for poly in polys for p in poly[0]]; ys = [p[1] for poly in polys for p in poly[0]]
            w, s, e, n = min(xs), min(ys), max(xs), max(ys)
            mine = []
            for gy in range(int(s * 100), int(n * 100) + 1):
                for gx in range(int(w * 100), int(e * 100) + 1):
                    for cl in grid.get((gy, gx), ()):
                        k = (cl[0], cl[1])
                        if k in used or not (s <= cl[3] <= n and w <= cl[4] <= e):
                            continue
                        if contains(polys, cl[4], cl[3]):
                            used.add(k); mine.append(cl)
            pr = ft["properties"]
            pr["t"] = sum(1 for m in mine if m[2] in (0, 1))
            pr["t9"] = sum(1 for m in mine if m[2] == 2)
            if pr["t"] + pr["t9"] >= 2:
                mine.sort()
                r0, c0 = mine[0][0], mine[0][1]
                flat = []
                for m in mine:
                    flat += [m[0] - r0, m[1] - c0, m[2]]
                out.append({"k": pr["k"], "c": pr["c"], "cn": pr["cn"], "n": pr["n"], "lp": pr["lp"],
                            "t": pr["t"], "t9": pr["t9"], "h": pr["h"], "o": pr.get("o"), "d": pr.get("d"),
                            "bb": [round(s, 5), round(w, 5), round(n, 5), round(e, 5)],
                            "r0": r0, "c0": c0, "m": flat})
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
    out.sort(key=lambda a: -(a["t"] + a["t9"]))
    with open(os.path.join(AREAS, "nerai.json"), "w", encoding="utf-8") as f:
        json.dump({"v": 1, "src": "国交省 土地利用細分メッシュ(1976/1987/1991/1997)＋令和2年国勢調査 町丁", "areas": out},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(f"マス {len(cells)} / 町丁に入った {len(used)} / ランキング対象 {len(out)}町丁 "
          f"/ nerai.json {os.path.getsize(os.path.join(AREAS, 'nerai.json')) // 1024}KB")


if __name__ == "__main__":
    main()
