# -*- coding: utf-8 -*-
"""
build-svyear.py -- 100mマスごとのストリートビュー撮影年（metadata は無料）。v9.647
下田さん(2026-11-13)「2025年の新しいストリートビューのエリアを優先して歩きたい。年で分けて表示したい」

対象: areas/nerai.json の狙いの団地のマス（＝探す価値のある所）。マスの中心から半径60m以内のパノラマの撮影年。
出力: areas/svyear.json  {"v":1,"cells":[[行,列,年],...]}  年=0 はストリートビュー無し
使い方: python scripts/build-svyear.py   （鍵 ~/.gmaps_key を使う。途中で止めても続きから）
"""
import json, os, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = open(os.path.expanduser('~/.gmaps_key')).read().strip()
OUT = os.path.join(ROOT, 'areas', 'svyear.json')


def tky2jgd(lat, lon):
    return (lat - 0.00010695 * lat + 0.000017464 * lon + 0.0046017, lon - 0.000046038 * lat - 0.000083043 * lon + 0.010040)


def main():
    cells = []
    for a in json.load(open(os.path.join(ROOT, 'areas', 'nerai.json'), encoding='utf-8'))['areas']:
        for i in range(0, len(a['m']), 4):
            cells.append((a['r0'] + a['m'][i], a['c0'] + a['m'][i + 1]))
    if '--all' in sys.argv:   # v9.648: 県内の「家が建っている100mマス」全部（areas/*.geojson の hc）
        import glob
        for fn in sorted(glob.glob(os.path.join(ROOT, 'areas', '1*.geojson'))):
            for ft in json.load(open(fn, encoding='utf-8'))['features']:
                hc = ft['properties'].get('hc') or []
                for i in range(2, len(hc), 2):
                    cells.append((hc[0] + hc[i], hc[1] + hc[i + 1]))
    cells = sorted(set(cells))
    done = {}
    if os.path.exists(OUT):
        for r, c, y in json.load(open(OUT))['cells']:
            done[(r, c)] = y
    todo = [k for k in cells if k not in done]
    print('マス', len(cells), '残り', len(todo), flush=True)

    def one(k):
        la, lo = tky2jgd((k[0] + .5) / 1200, 100 + (k[1] + .5) / 800)
        for _ in range(3):
            try:
                m = json.load(urllib.request.urlopen('https://maps.googleapis.com/maps/api/streetview/metadata?' + urllib.parse.urlencode(
                    {'location': f'{la},{lo}', 'radius': 60, 'source': 'outdoor', 'key': KEY}), timeout=30))
                return k, (int(str(m.get('date', '0'))[:4]) if m.get('status') == 'OK' else 0)
            except Exception:
                time.sleep(1)
        return k, None
    n = 0
    with ThreadPoolExecutor(8) as ex:
        for k, y in ex.map(one, todo):
            if y is not None:
                done[k] = y
            n += 1
            if n % 2000 == 0:
                json.dump({'v': 1, 'cells': [[a, b, v] for (a, b), v in sorted(done.items())]}, open(OUT, 'w'), separators=(',', ':'))
                print(n, flush=True)
    json.dump({'v': 1, 'cells': [[a, b, v] for (a, b), v in sorted(done.items())]}, open(OUT, 'w'), separators=(',', ':'))
    from collections import Counter
    print('撮影年', sorted(Counter(done.values()).items()), 'DONE', flush=True)


if __name__ == '__main__':
    main()
