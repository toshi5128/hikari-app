# ひかり不動産アプリ — Claude Code 作業ルール

このファイルはセッション開始時に自動で読み込まれる。**毎回ここを守ること。**
詳細な業務仕様・保護フィールド・過去事故は [HANDOFF.md](HANDOFF.md) に集約してある。

---

## 🚨 最重要：巨大ファイルの扱い方

`index.html` は **約17,000行・900KB超**。これが事故とコンテキスト枯渇の最大要因。

1. **`index.html` 全体を Read しない。** 一度に全部読むとコンテキストが一気に膨らむ。
2. コードを探すときは **まず Grep（`-n` で行番号付き）** で該当箇所を特定する。
3. Read するのは **ヒット周辺の必要な行範囲だけ**（`offset` / `limit` を使う）。
4. 修正は全体書き換えではなく **Edit によるピンポイント編集**。`old_string` は最小限・一意に。
5. 不明点を「全体スキャンで把握しよう」としない。**Grep で絞ってから**確認する。
6. 大きな調査・長い作業は**分割**する。1タスク終わったら区切る。

---

## 🔧 変更〜デプロイの手順（毎回）

1. **`APP_VERSION` を bump する**（必須）。形式 `vM.m[.p]`、数値比較されるので桁に注意。
   - 場所: `index.html` 冒頭付近の `const APP_VERSION = "..."`
2. **ビルドで構文検証**（push前に必ず）:
   ```
   npm run build
   ```
   - Node v24 は `%LOCALAPPDATA%\Programs\nodejs`（bash の PATH 外）。PowerShell から実行。
   - 出力 `dist/index.html` のサイズが極端に小さくないか確認。
3. `index.html` を commit → `git push`。
   - GitHub Actions（`deploy.yml`）が `dist/` を自動ビルドして Pages 配信。
   - `dist/` は **gitignore**。手で add しない（CIが生成する）。

---

## 🛡 データ保護（絶対厳守）

ユーザー（営業担当全員）がアプリで手入力したデータは **アップデートで絶対に書き換えない**。

- 保護フィールド: `status` / `memo` / `assignee` / `dm` / `visit` / `visitLog` / `landmark` / `lat` / `lng` / `createdAt` ほか（全リストは HANDOFF.md CHECK 7）
- `setData` は **最小差分**で。該当 id の該当フィールドだけ更新し、`updatedAt` と `_fieldUpdatedAt.<key>` を明示更新。
- **既存フィールドを `delete` しない**（リモートに残ると同期で復活する。`false`/`""` をセットする）。
- `mergeItems` / `saveToSupabase` の RMW・同期ロジックには触らない。
- UI/見た目だけの変更時は `data.jiage` 等の中身に触らない。

迷ったら HANDOFF.md の「CHECK 7 自己チェックリスト」を通すこと。

---

## 📐 売買価格査定書サーバー（別リポジトリ）

査定書の生成エンジンは **`C:\Users\st106\hikari-satei`**（このアプリとは別）。
- アプリ側 `sendToSateiServer(data, fmt)` が会社PCのFlaskサーバー（`/generate?fmt=pdf|xlsx`）に投げる。
- サーバーURLは ntfy.sh トピック経由で自動取得（手貼り不要）。
- エンジン本体・テンプレート・サーバーを触るときは `hikari-satei` 側を見る。

---

## 参照

- 業務仕様・マージロジック・判定列・過去事故 → **[HANDOFF.md](HANDOFF.md)**
- 主要定数（メンバー・エリア・ステータス・Supabase接続）→ HANDOFF.md「重要な定数」
