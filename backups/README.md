# 🔒 自動バックアップ

このフォルダには、Supabase上の本番データの日次バックアップが保存されます。

## 仕組み

GitHub Actions が **毎日 JST 11:00** に自動で `app_data` テーブル全体を JSON で取得し、`hikari_main_YYYY-MM-DD_HH-MM.json` として保存します。

直近 30 日分を保持し、それ以前は自動で削除されます。

## 手動実行

すぐにバックアップを取りたい場合:

1. GitHub の **Actions** タブを開く
2. 左サイドバーから **"Daily Backup"** を選択
3. 右上の **"Run workflow"** ボタン → **"Run workflow"** を押す

## データを戻したい場合

万一データが消えたり壊れたりした場合、以下の手順で復元できます。

1. このフォルダから戻したい日付の JSON を選ぶ
2. JSON の中身は `[{"data": { ... 実データ ... }}]` という形なので、`data` の中身を取り出す
3. Supabase のダッシュボード または curl で `app_data` テーブルの `id=hikari_main` の `data` 列を上書き

復元は重大なオペレーションなので、必ず Cowork に相談してください。
