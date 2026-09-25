---
name: hikari-stats
description: ひかり不動産アプリ(hikari-app)の数字をSupabaseから読むだけで集計して答える。「今週の地番待ちは何件？」「DM未送付の空き家は？」「謄本待ちは？」「見込みは誰が何件？」「今週どれくらいピン立てた？」など、地上げピンの件数・内訳を聞かれたときに使う。
---

# ひかりアプリの集計に答える（読むだけ）

下田さんから「アプリの数字」を聞かれたら、このフォルダの `sql/` にある集計SQLを
Supabase MCP の `execute_sql` で実行し、結果を**素人言葉で短く**答える。

- プロジェクトID: `ckcykbvislsjwvkizkqc`（テーブル `app_data`）
- 地上げピンは `app_data` の `id = 'jiage::<ピンid>'` の行（1件=1行）。`data.item` がピン本体。
- 削除済み（`hikari_main` の `data.tombstones.jiage`）と個人保有（`personalOwner`）は数えない＝アプリの「会社の数字」と同じ。

## 🚨 絶対に守ること

1. **実行してよいのは `select`（`with ... select`）だけ。** `insert` / `update` / `delete` / `alter` / `create` / `drop` / `truncate` / `grant` などは一文字も書かない。
2. `apply_migration`・`deploy_edge_function`・ブランチ操作など、**書き込み系の Supabase ツールは使わない。**
3. `app_data` の `hikari_main` 行（約4MB）を `select data` で丸ごと取らない。必要な項目だけ `->` / `->>` で取り出す。
4. 所有者名・住所の一覧を出すのは、下田さんが「一覧で」と頼んだときだけ。件数で足りるなら件数だけ。

## どのSQLを使うか

| 聞かれ方の例 | ファイル |
|---|---|
| 「ピン全部で何本？」「謄本待ち/要修正/訪問OKは何件？」 | `sql/01_overview.sql` |
| 「地番待ちは何件？」「今週の地番待ちは？」「誰の地番待ちが多い？」 | `sql/02_chiban_wait.sql` |
| 「DM未送付の空き家は？」「DMまだの所は何件？」 | `sql/03_dm_unsent.sql` |
| 「見込みは何件？」「ステータス別に」「〇〇さんの再訪は？」 | `sql/04_status_by_member.sql` |
| 「今週どれくらい動いた？」「今週立てたピンは？」「先週と比べて」 | `sql/05_this_week.sql` |

ファイルを Read して中身をそのまま `execute_sql` の `query` に渡す（先頭のコメントも付いたままで良い）。

### 5本に当てはまらない質問

`sql/00_base.sql` の `with tomb as ... p as (...)` までをそのまま使い、最後の `select ... from p` だけを書き換える。
`p` で使える列:

| 列 | 意味 |
|---|---|
| `pin_id`, `assignee`(担当), `area`(エリア), `status`(営業ステータス), `address`(地番), `landmark`(目印住所), `owner`(所有者名) | 文字 |
| `stage` | 5状態: 🟡地番待ち / ⏳謄本待ち / 🚪訪問OK / 🚫対象外 / 🛑取れない / 🔧要修正 / その他(取込ピン) |
| `dm`, `dm_sent`(送付回数), `dm_stopped`(不要・反応・返送で止まっている) | DM |
| `created_at`, `updated_at` | 立てた日時・最後に更新した日時（timestamptz。JSTで見せるときは `at time zone 'Asia/Tokyo'`） |
| `week_start` | 今週の月曜0時(JST) |
| `j` | ピン丸ごと(jsonb)。上に無い項目は `j->>'項目名'` で |

## 答え方

- 結論（数字）を1行目に。「地番待ちは **23件**（うち今週立てた分 5件）。多いのは長島さん 9件」のように。
- 担当別・エリア別は表で。上位だけで良い。
- 数字がアプリ画面とずれそうなとき（DM未送付は法人所有・本人居住の除外がアプリ側だけ）は一言添える。
- 何か「決め」が出たら、判断軸を thought-engine に一行残すよう促す（CLAUDE.md の習慣）。

## うまく動かないとき

- `execute_sql` が許可待ちで止まる → 下田さんに「Supabaseの読み取りを許可してください」と伝える。勝手に別の手段（REST直叩き等）で回避しない。
- SQLエラー → エラー文を見て `sql/00_base.sql` の共通部分を直し、`python make_sql.py` で 01〜05 を作り直す（直すのはこのフォルダのファイルだけ。DB側は触らない）。
