# ひかり不動産アプリ 引き継ぎドキュメント（2026-06-03 v8.107時点）

このドキュメントは、Cowork セッションで実装した内容を Claude Code 側で続きの作業を行うための引き継ぎ資料です。

---

## 📌 TL;DR（最重要・3行）

- **現在の本番バージョン: v8.107-confirmed-chip**（GitHub Pages にデプロイ済み・全端末配信中）
- **デプロイ方式: GitHub Actions が `dist/index.html`（事前コンパイル版）を Pages に直接配信**（main の `index.html` は JSX ソース版、Pages 配信元は GitHub Actions）
- **直近の最重要機能: 地上げの「現地ピン 2段構え」（v8.95-v8.107 で構築。地番待ち→確定→謄本取得 のワークフロー）**

---

## 🌐 アプリ概要

- **名前**: ひかり不動産 PWA（社内 CRM / 業務支援アプリ）
- **対象業務**: 不動産仕入営業（地上げ＝空き家・所有者へのアタック）、仲介、在庫管理、積算、営業日報、メンバー間カレンダー共有
- **公開先**: https://toshi5128.github.io/hikari-app/
- **GitHubリポジトリ**: toshi5128/hikari-app
- **データ保存先**: Supabase（プロジェクト `ckcykbvislsjwvkizkqc`、テーブル `app_data`、id=`hikari_main`、`data` 列に JSON 全データ）
- **ローカルキャッシュ**: `localStorage.hikari_v4_cache`

## 🛠 技術スタック

- **HTML 1ファイル構成**（`index.html`、現在約 16,000 行・900KB）
- **React 18** + JSX、`<script type="text/plain" id="hikari-jsx-src">` 内に記述
- **ビルド**: `tools/build.mjs`（Node + `@babel/core` + `@babel/preset-react`）が JSX を事前コンパイルして `dist/index.html` を生成
- **デプロイ**: `.github/workflows/deploy.yml` が push 時に自動ビルド＆Pagesデプロイ
- **GitHub Pages の Source**: 「GitHub Actions」（Settings → Pages）
- **地図**: Leaflet 1.9.4 + OpenStreetMap タイル
- **同期**: 15秒ポーリング、tombstone（削除確定）、`_fieldUpdatedAt`（フィールド単位の更新時刻）、保存前 RMW（read-modify-write）

## 🔄 GitHub Actions（3つ稼働中）

| ワークフロー | ファイル | 用途 | トリガ |
|---|---|---|---|
| Deploy to Pages | `deploy.yml` | 本番デプロイ | push to main / 手動 |
| Preview Build | `preview-build.yml` | 検証用ビルド成果物（artifact のみ） | push to main / 手動 |
| Daily Backup | `backup.yml` | Supabase の JSON を `backups/` フォルダにコミット | 毎日 JST 11:00 / 手動 |

---

## 🆕 最新の主要機能群

### 🗺 地上げ「現地ピン」機能（v8.95-v8.107 で構築）

**コンセプト**: 現場でピンを立てて空き家を認定 → 後で地番を入力 → 謄本取得 → DM 送付フェーズへバトンタッチ

#### ワークフロー（運用フロー）

| Step | 担当 | 操作 | データ変化 |
|---|---|---|---|
| 1 | 現場担当者 | アプリの地図で「📍 現在地で立てる」or「🗺 地図タップで立てる」 | `jiage` に `coordsManual:true, address:"", landmark:"目印", lat/lng:実測` 追加。**🟡 地番待ち** で表示 |
| 2 | 確認担当 | 「✅ 確定済み」チップから or 直接ピンタップ → 編集モーダルで地番を入力 | `address` が埋まる。🟡 が消えて通常色（未訪問）に |
| 3 | オペレーター | 「📥 現地ピンCSV出力」（＋ボタンメニュー） | 確定済みのみ CSV ダウンロード（地番待ちは除外） |
| 4 | **Claude Code** | CSV を使って謄本（登記簿）を一括取得し、所有者氏名/住所を付加してスプレッドシートに集約 | 別システムで処理（このアプリ外） |
| 5 | オペレーター | スプレッドシートをアプリにインポート（「＋」→「📥 Excel/CSVをインポート」） | jiage に所有者情報付きで登録（status="未訪問" がデフォルト） |
| 6 | 営業担当 | DM 発送・訪問アタック・成果記録 | 既存の地上げ業務フロー |

#### データスキーマ（jiage の現地ピン関連フィールド）

```js
{
  id: 1780466234567,          // Date.now()
  address: "深谷市常盤町68-11", // 地番（空 = 地番待ち）
  landmark: "深谷市本田",       // 🆕 目印住所（逆ジオコで自動入力、手入力可）
  lat: 36.187531,              // 実測座標（保護される）
  lng: 139.284321,             // 実測座標（保護される）
  assignee: "下田",             // 立てた担当者
  memo: "築古・空き家っぽい",
  status: "未訪問",
  dm: "未",
  visit: "未",
  coordsManual: true,          // 🆕 ジオコーディング保護フラグ（runGeocoding 対象外）
  source: "現地ピン",          // 🆕 識別用
  area: "深谷",                 // 自動判定（住所から JIAGE_AREAS と照合）
  createdAt: 1780466234567,    // 立てた日時（halo判定・集計に使用）
  updatedAt: 1780466234567,
  ownerName: "",                // 後でインポートで埋まる
  ownerAddr: "",                // 後でインポートで埋まる
  history: [], visitLog: [], family: [],
}
```

#### 視覚的な区別

| 状態 | ピンの色 | バッジ | 備考 |
|---|---|---|---|
| 地番待ち（coordsManual && address空） | 🟡 #fbbf24 | `?` バッジ | 「✅ 確定済み」 から外れる |
| 今日 + 地番待ち | 🟡 + 金色 halo（パルス） | `?` + 「今日」 | 確定すると halo 消える |
| 地番確定済み（coordsManual && address入り） | グレー（未訪問通常色） | なし | 通常の地上げピンと同じ見え方 |
| インポート物件（!coordsManual） | ステータス色 | 状況に応じて | 通常運用 |

#### 操作 UI（地上げタブ → 🗺地図 モード）

```
🔍 [住所・地名で地図移動（例: 小川町、東松山市本田）______] [移動] [✕]

📍 現地ピン操作パネル
[📍 現在地で立てる] [🗺 地図タップで立てる] [🧭 現在地へ] [🎯 全件表示]
🛰️ 現在地: 36.187, 139.284 (±15m)
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
📍 現地ピン合計  12件 (要 地番入力)  / ✅確定 7件    ※ 今日新規 4件
[📍 全体: 12件] [下田: 5件] [比嘉: 4件] [長島: 3件]  [✅ 確定済み: 7件]
💡 チップを押すと「現地ピンのみ」に絞り込み（インポート物件は除外）
```

#### 関連する主要関数（コード上の位置）

- `reverseGeocode(lat, lng)` (line ~11086): OpenStreetMap Nominatim で日本語の市区町村+町名を取得
- `geocodeAddress(addr)` (line ~11045): 国土地理院 API で住所→座標（既存）
- `runGeocoding(target)` (line ~11941): 一括ジオコーディング。**`coordsManual:true` は対象外**（保護）
- `saveOnsitePin()` (line ~11500): 現地ピン保存。`approaches.values["新規地上"]` を自動 +1
- `pendingPinSummary` useMemo (line ~11400): 地番待ち集計（担当者別＋今日新規＋確定済み件数）
- `downloadOnsitePinCSV()` (line ~11580): 確定済みのみを CSV ダウンロード
- `LeafletMap` コンポーネント (line ~3386): 新prop多数（`onMapClick`, `currentLocation`, `centerOnLocationKey`, `fitBoundsKey`, `panToCoords`, `panToCoordsKey`）

---

## ⚠️ Claude Code 側でチェック/注意すべきこと

### 🔴 [CHECK 1] インポート時の現地ピンとの重複処理（最重要）

**シナリオ:**
- Step 1 で立てた現地ピン: `address="深谷市常盤町68-11"`, `ownerName=""`, `coordsManual:true`, `lat/lng=実測`
- Step 5 でインポートする行: `address="深谷市常盤町68-11"`, `ownerName="山田太郎"`, `ownerAddr="..."`

**現在のインポート重複判定ロジック**: 「物件住所＋所有者で重複判定」（v8.91 で実装）

**懸念**: 既存の現地ピンが `ownerName=""` で、インポート行が `ownerName="山田太郎"` の場合、所有者が異なるため**別物と判定 → 2件できる可能性**がある。

**理想の挙動:**
- 同じ地番（address）なら既存の現地ピンに**マージ**して、`ownerName` と `ownerAddr` のみ追加
- `coordsManual:true`、`lat/lng=実測`、`landmark`、`createdAt`、`assignee` は維持

**Claude Code 側で実装を確認/補強すべき点:**

1. **インポート時の重複判定ロジックを「coordsManual:true の既存と address だけマッチした場合は ownerName 不問でマージ」に拡張**
   - 該当箇所: `index.html` の `convertSheet()` + その後の重複処理（grep: `mergedJiage` あたり）

2. **マージ時の実測座標保護**
   - 既存の `coordsManual:true` ピンに対しては、インポート側の lat/lng で**絶対に上書きしない**
   - 同様に `landmark`, `createdAt`, `source: "現地ピン"` も保護
   - ownerName/ownerAddr/area などの「インポート側で埋まる項目」のみ更新

3. **マージ後の `source` 維持**
   - 元が「現地ピン」だったレコードはずっと「現地ピン」由来として識別可能であるべき
   - 必要なら `source: "現地ピン+インポート"` のような複合表現も検討

**テスト方法:**
1. アプリで現地ピンを1件立てる（地番: 例 "深谷市常盤町68-11"、所有者は空）
2. Claude Code 側で同じ地番に所有者を付加したスプレッドシートを作成
3. アプリにインポート
4. 結果が **1件のレコード**で、所有者情報が追加されているか確認
5. `lat/lng` が実測値（小数点6桁以上の精緻な値）のままか確認

### 🟡 [CHECK 2] CSV出力 → スプレッドシート → インポート の列マッピング

**現在の「📥 現地ピンCSV出力」の列構成:**

```
ID / 作成日 / 地番 / 目印住所 / 担当者 / 緯度 / 経度 / ステータス / メモ
```

**インポート時に期待する列構成（Claude Code 側で集約後）:**

- 「地番」→ アプリの `address` フィールドにマップ
- 「所有者氏名」→ `ownerName`
- 「所有者住所」→ `ownerAddr`
- 「緯度」「経度」→ アプリ側で既存の `lat/lng` が保護される（インポート側のは無視 or 補助）
- 「担当者」→ `assignee`
- 「ID」→ もしマージのキーとして使うなら必須

**Claude Code 側で確認すべきこと:**

- スプレッドシートの列名がアプリのインポート機能の認識する列名と合っているか
- 既存のインポート列マッピング（`convertSheet` 内）を確認: address, owner, ownerAddr, ownerContact, assignee, date, area, lat, lng, dm, visit, status, bikou, memo
- 「ID」列をマージキーとして使う方針なら、インポート側も「ID」を見るよう改修が必要

### 🟢 [CHECK 3] 既存データの保護（過去のv8.80事故再発防止）

**事故事例**: v8.80 で「デモデータ削除」の意図でデモ名を含む実データまで消えた

**Claude Code 側で守るべきルール:**

1. **着手前に Supabase の app_data(id=hikari_main) を必ずバックアップ**（`backup.yml` 手動実行可能、または `backups/` フォルダから最新を確認）
2. **データを「名前部分一致」で対象選定する破壊的処理は絶対書かない**
3. **既存スキーマのフィールドを削除/リネームしない**（追加は可）
4. **インポート/マージ処理の改修時、既存レコードの DM・住確・メモ・売上・在庫・実測座標を上書きしない**
5. **APP_VERSION を bump する**（更新バナーが出ない/更新が伝搬しない）

### 🟢 [CHECK 4] バージョン文字列の比較ロジック（v8.102 で修正済み）

過去のバグ: 「v8.98 > v8.101」が文字列比較で TRUE になり、無限更新ループ発生

**v8.102 で `isRemoteVersionNewer()` を正規表現で数値パース比較に修正済み**

Claude Code 側でも:
- バージョン文字列を作るときは `YYYY-MM-DD-vM.m[.p]-<note>` 形式を守る
- 文字列比較ではなく数値比較を使う（既に修正済みだが念のため）

---

## 🛡️ 重要な制約・安全規則（必読）

1. **Supabaseへの書き込み前に必ずバックアップ**（`backup.yml` 手動実行 or `backups/` フォルダ）
2. **既存データの構造を破壊する移行スクリプトを書かない**（スキーマ追加は OK）
3. **APP_VERSION の bump は必須**
4. **`runGeocoding` の対象から `coordsManual: true` を除外**（実測座標を上書きしない）
5. **インポート時のマージ仕様を維持**: 「DM・住確・メモは空/未では上書きしない」（v8.91 で実装済み）+ 上記 CHECK 1 で現地ピン保護を追加
6. **同期ロジックを変更する時は `tombstones` / `_fieldUpdatedAt` / `protectedKeys` の関係を理解した上で**（v8.73-v8.89 の長い修正履歴あり）
7. **データを多端末で扱うので、操作前に他端末の状態を考慮**（古いキャッシュとの競合に注意）

### 同期の仕組み（概略）

- 配列フィールド（`stocks`, `jiage`, `approaches`, `mediations`, etc.）はアイテム単位で `mergeItems()` でマージ
- 上位アイテムの削除は **top-level `data.tombstones.{key}.{id}: timestamp`** で確定（30日間保持）
- ネスト配列（`viewings`, `visitLog`, `photos`, `family`）は親アイテムごとの `{nested}Tombstones`
- field-level 更新時刻で arbitration（特定キー: `adminMembersUpdatedAt` 等）
- 保存前に Supabase を読み直して union マージしてから書き戻し（v8.63 RMW）

---

## 📁 重要ファイルマップ

```
hikari-app/
├── index.html                     # 本体（16K行、JSX）
├── manifest.json                  # PWA
├── sw.js                          # Service Worker
├── package.json                   # @babel/core, @babel/preset-react
├── tools/
│   ├── build.mjs                  # 事前コンパイル
│   └── README.md
├── .github/workflows/
│   ├── deploy.yml                 # 本番デプロイ（Pages: GitHub Actions）
│   ├── preview-build.yml          # 検証用ビルド成果物
│   └── backup.yml                 # 日次バックアップ
├── backups/                       # 自動バックアップ JSON（直近30日）
├── dist/                          # gitignore。ビルド成果物
└── HANDOFF.md                     # このファイル
```

---

## 🗂 重要な定数 / データ構造

```js
// 地上げステータス
const ATTACK_STATUSES = ["未訪問","初訪","再訪","見込み","中長期見込","見込無し","交渉中","媒介","仕入"];

// 地上げステータスの色（v8.87）
const JIAGE_STATUS_COLORS = {
  "未訪問": "#94a3b8", "初訪": "#0ea5e9", "再訪": "#2563eb",
  "見込み": "#22c55e", "中長期見込": "#fbbf24", "見込無し": "#ef4444",
  "交渉中": "#f97316", "媒介": "#a855f7", "仕入": "#06b6d4",
};

// 地上げエリア（v8.91 で「小川」追加）
const JIAGE_AREAS = ["熊谷", "行田", "深谷", "東松山", "本庄", "秩父", "上里", "小川"];

// 訪問結果
const VISIT_RESULTS = [
  { key: "home",     label: "🤝 面談",     autoStatus: "初訪" },
  { key: "ignore",   label: "🚪 居留守",   autoStatus: "初訪" },
  { key: "absent",   label: "🚫 不在",     autoStatus: "初訪" },
  { key: "rejected", label: "⛔ 訪問禁止", autoStatus: "初訪" },
];

// メンバー
const MEMBERS = ["たっくん","長島","松村","脇本","谷津","下田","比嘉","比嘉・下田"];

// 管理者（v8.86 で複数対応）
data.adminMembers = ["下田", "比嘉"];     // 配列
data.adminMember = "下田";                // 後方互換の単数
data.adminMembersUpdatedAt = <ts>;        // v8.89 端末跨ぎ同期用
```

---

## 📜 バージョン履歴

| ver | 主な変更 |
|---|---|
| v8.86 | 複数管理者対応（下田＋比嘉） |
| v8.87-88 | 地上げステータス色分け・NG赤枠 |
| v8.89 | 管理者リスト端末跨ぎ同期バグ修正 |
| v8.90-91 | Claude Code: 小川エリア追加・ピン座標ナビ・取込時DM/住確保護 |
| v8.92 | Babelコンパイル結果キャッシュ |
| v8.93 | UX 4種（月切替バッジ・決済日アラート・反響顧客名検索） |
| v8.94 + Phase 3 | 自動バックアップ＋本番ビルドパイプライン |
| **v8.95** | **現地ピン基本機能（GPS+地図タップ）** |
| **v8.96** | **地図UX改善（高さ拡大・ズーム保持・全件表示）** |
| **v8.97** | **エリア自動判定＋保存後パン** |
| **v8.98** | **2段構え化（目印住所＋地番、地番待ち）** |
| **v8.99** | **今日立てたピンを金色halo＋「今日」バッジで強調** |
| **v8.100** | **担当者別集計＋新規地上カウンタ自動連動** |
| **v8.101** | **詳細・編集UI改善（地番確定フロー完成）** |
| **v8.102** | **isRemoteVersionNewer 数値比較化（v8.98 > v8.101 誤判定修正）** |
| **v8.103** | **ピンに「誰が・いつ」を明示** |
| **v8.104** | **カウンタを「未処理ToDo（地番待ち）」に方針転換** |
| **v8.105** | **チップ押下時にインポート物件除外（現地ピンのみ表示）** |
| **v8.106** | **地図に住所/地名検索バー追加** |
| **v8.107** | **「✅ 確定済み」チップ追加（確定後の混乱解消）** |

---

## 🚧 未着手の改善案

### Phase 4: コード分割（保守性向上・優先度低）

`index.html` の 16,000 行を機能ごとに分割（要 Phase 3 ビルドパイプライン）

### 機能追加候補

1. ホーム画面に「自分の今日のToDo」枠
2. グローバル検索（タブをまたいだ全文検索）
3. データ完全性ダッシュボード（売契完了で売決日空 / 仕契完了で仕決日空 など）
4. 在庫・地上げ・反響・積算の Excel/CSV エクスポート
5. 物件のシェアリンク（`?stock=123` 形式）
6. @メンション機能（コメント `@比嘉` でプッシュ通知）
7. 写真の GPS 情報（EXIF）から位置自動抽出
8. 操作履歴（監査ログ）強化
9. 2要素認証（4桁パスワード補強）
10. ゴミ箱機能（30日以内なら復元可能）

### 既知の懸念

- **インポート時の現地ピン重複処理**（上記 CHECK 1 参照、要 Claude Code 確認・改修）

---

## 🔑 こまかいけど重要なこと

### Supabase 認証情報（index.html 上部に直書き）

```
SUPABASE_URL = "https://ckcykbvislsjwvkizkqc.supabase.co"
SUPABASE_KEY = "<anon key>"  // 公開して問題ない anon キー
DATA_ID = "hikari_main"
```

### バックアップ JSON の構造

```json
[
  {
    "data": {
      "stocks": [...],
      "jiage": [...],
      "approaches": [...],
      "mediations": [...],
      "owners": [...],
      "yakusho": [...],
      "sekisan": [...],
      "customEvents": [...],
      "activityLog": [...],
      "tombstones": {...},
      "migrations": {...},
      "memberPasswords": {...},
      "memberGoals": {...},
      "annualGoals": {...},
      "adminMembers": [...],
      "adminMember": "...",
      "adminMembersUpdatedAt": ...,
      "notifyMembers": [...],
      "counterCustom": {...},
      "__appVersion": "..."
    }
  }
]
```

### 過去事故の記録（必読）

- **v8.80 事故**: デモデータ削除のつもりが、デモ名と同じ名前のついた本物の在庫データを削除してしまった。教訓: **「○○という名前を含む」のような broad な削除ロジックは絶対書かない**
- **v8.86 → v8.89 の管理者同期バグ**: protectedKeys に adminMembers を入れたせいで、他端末で行った管理者追加が反映されなくなった。教訓: **「直近5分編集ガード」は強力すぎるので field-level updatedAt に置き換えるべき**
- **v8.101 → v8.102 のバージョン比較バグ**: 文字列比較で "v8.98" > "v8.101" が TRUE になり、無限更新ループに陥った。教訓: **バージョン比較は必ず数値パースで**

---

## 🤝 引き継ぎコメント

このセッションで以下を一気にやりました:
- 過去事故（v8.80）のデータ調査と原因特定
- v8.86-v8.107 の機能追加・バグ修正（特に現地ピン機能を v8.95-v8.107 で大幅構築）
- ビルドパイプラインと本番デプロイ切替（Phase 3 完了）
- 自動バックアップ仕組みの構築

**Claude Code 側で次にやってほしいことの優先順:**

1. **[CHECK 1] インポート時の現地ピン重複処理を確認＆改修**（最重要）
   - `convertSheet` のあとの重複判定ロジックを `coordsManual:true` ケースで拡張
   - 既存ピンの実測座標・landmark・createdAt・source を保護
2. **謄本取得スクリプトを CSV 入力に対応**
   - 「📥 現地ピンCSV出力」が出力する列構成（ID/作成日/地番/目印住所/担当者/緯度/経度/ステータス/メモ）を入力にできるように
3. **謄本取得結果スプレッドシートのフォーマットを決める**
   - インポート時にアプリの列マッピングと合う形にする
   - 「ID」列を残しておくとマージのキーになる（理想動作には CHECK 1 の改修も必要）

何かあれば、`backups/` フォルダの自動バックアップから復元できます。
