# 01〜05 の集計SQLを作り直す。共通部分(00_base.sql の with 句)を直したら `python make_sql.py` を実行する。
# ここで作るSQLはすべて「読むだけ(select)」。
import io
import os

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sql")
src = io.open(os.path.join(HERE, "00_base.sql"), encoding="utf8").read()
base = src[src.index("with tomb as"):src.rindex("select count(*) as pins from p;")]

FILES = {
    "01_overview.sql": (
        "-- ① 全体のピン数と段階別の内訳（「ピン何本ある？」「謄本待ちは何件？」）",
        """select stage as 段階, count(*) as 件数
from p group by stage
union all
select '【合計】', count(*) from p
order by 件数 desc;
"""),
    "02_chiban_wait.sql": (
        "-- ② 地番待ち（ピンは立てたが地番が未入力）を担当者別に。今週立てた分も（「今週の地番待ちは何件？」）\n"
        "-- 担当が「(合計)」の行が全員分。",
        """select coalesce(assignee, '(合計)') as 担当,
       count(*) as 地番待ち,
       count(*) filter (where created_at >= week_start) as うち今週立てた分,
       min(created_at at time zone 'Asia/Tokyo')::date as 一番古い日
from p where stage = '🟡地番待ち'
group by rollup(assignee)
order by grouping(assignee), 地番待ち desc;
"""),
    "03_dm_unsent.sql": (
        "-- ③ DM未送付の空き家（所有者と送り先住所が分かっていて、まだ1通も送っていないもの）\n"
        "-- 除外: 訪問禁止 / 対象外(excluded) / DM停止(不要・反応・返送)。\n"
        "-- 法人所有・本人居住・氏名崩れの除外はアプリ側だけの判定なので、画面の「送付対象」と数件ずれることがある。\n"
        "-- 担当・エリアが空欄(null)の行は小計/合計。",
        """select assignee as 担当, area as エリア, count(*) as DM未送付
from p
where has_owner and has_owner_addr and not excluded and not dm_stopped
  and status <> '訪問禁止' and dm <> '📩返送' and dm_sent = 0
group by rollup(assignee, area)
order by grouping(assignee), assignee, grouping(area), DM未送付 desc;
"""),
    "04_status_by_member.sql": (
        "-- ④ 営業ステータス（未訪問・再訪・見込み…）を担当者別に（「見込みは誰が何件？」）",
        """select status as ステータス,
       sum(n) as 合計,
       jsonb_object_agg(assignee, n order by n desc) as 担当別
from (select status, assignee, count(*) as n from p group by status, assignee) s
group by status
order by 合計 desc;
"""),
    "05_this_week.sql": (
        "-- ⑤ 今週と先週の動き（新しく立てたピン・更新されたピン）を担当者別に（「今週どれくらい動いた？」）\n"
        "-- 担当が「(合計)」の行が全員分。週は JST の月曜0時始まり。",
        """select coalesce(assignee, '(合計)') as 担当,
       count(*) filter (where created_at >= week_start) as 今週の新規ピン,
       count(*) filter (where created_at >= week_start - interval '7 days' and created_at < week_start) as 先週の新規ピン,
       count(*) filter (where updated_at >= week_start) as 今週更新したピン
from p
group by rollup(assignee)
order by grouping(assignee), 今週の新規ピン desc, 今週更新したピン desc;
"""),
}

for name, (head, tail) in FILES.items():
    body = head + "\n-- 読むだけ（select のみ）。共通部分は 00_base.sql と同じ（make_sql.py で生成）。\n" + base + tail
    io.open(os.path.join(HERE, name), "w", encoding="utf8", newline="\n").write(body)
    print("wrote", name)
