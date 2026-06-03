# ひかり不動産アプリ 引き継ぎドキュメント

最終更新: 2026-06-03 (Cowork 作業セッション終了時点)

このドキュメントは、Cowork（Anthropic 公式デスクトップアプリ）でのセッションで実装した内容を、Claude Code 側で続きの「仕上げ」作業を行うための引き継ぎ資料です。

---

## 📌 TL;DR（最重要・3行）

- **現在の本番バージョン: v8.96-map-bigger-zoom-keep**（GitHub Pages にデプロイ済み・全端末配信中）
- **デプロイ方式: 事前コンパイル済みの `dist/index.html` を GitHub Actions が Pages に配信**（main の `index.html` は JSX ソース版。Pages 配信元は GitHub Actions）
- **直近の追加機能: 地上げタブの地図に「現地ピン」「現在地表示」「全件表示」機能（v8.95–v8.96）**

---

## 🌐 アプリ概要

- **名前**: ひかり不動産 PWA（社内 CRM / 業務支援アプリ）
- **対象業務**: 不動産仕入営業（地上げ＝空き家・所有者へのアタック）、仲介、在庫管理、積算、営業日報、メンバー間カレンダー共有
- **公開先**: https://toshi5128.github.io/hikari-app/
- **GitHubリポジトリ**: toshi5128/hikari-app
- **データ保存先**: Supabase（プロジェクト `ckcykbvislsjwvkizkqc`、テーブル `app_data`、id=`hikari_main`、`data` 列に JSON 全データ）
- **ローカルキャッシュ**: `localStorage.hikari_v4_cache`

## 🛠 技術スタック

- **HTML 1ファイル構成**（`index.html`、現在約 16,000 行）
- **React 18** + JSX、`<script type="text/plain" id="hikari-jsx-src">` に書かれている
- **ビルド**:
  - Phase 3 で導入。`tools/build.mjs`（Node + `@babel/core` + `@babel/preset-react`）が JSX を事前コンパイルして `dist/index.html` に出力
  - GitHub Actions の `.github/workflows/deploy.yml` が push 時に自動でビルド＆Pagesデプロイ
  - GitHub Pages の Source は **「GitHub Actions」**（Settings → Pages）
- **地図**: Leaflet 1.9.4 + OpenStreetMap タイル
- **同期**: 15秒ポーリング、tombstone（削除確定）、`_fieldUpdatedAt`（フィールド単位の更新時刻）、保存前 RMW

## 🔄 GitHub Actions（3つ稼働中）

| ワークフロー | 用途 | トリガ |
|---|---|---|
| `deploy.yml` (Deploy to Pages) | 本番デプロイ | push / 手動 |
| `preview-build.yml` (Preview Build) | ビルド成果物の artifact だけ生成（検証用） | push / 手動 |
| `backup.yml` (Daily Backup) | Supabase データを JSON で取得し `backups/` にコミット | 毎日 JST 11:00 / 手動 |

---

## 🆕 直近の追加機能（v8.95–v8.96）

### 仕様の出発点

ユーザー要望:
> 地上げの地図で、Googleマップ系のジオコーディング（住所→座標変換）だと地番レベルで位置がズレる。地図タップまたは現在地で**実測座標**をそのまま記録できるようにしたい。後で登記簿（謄本）の一括取得に使うので、地番＋座標が正確に取れることが重要。

### 実装した機能

#### 1) 現地ピン（v8.95）

- **地上げタブ → 🗺 地図** に切替えると、地図上に新しい操作パネルが表示
- **「📍 現在地で立てる」**: GPSの現在地座標で即座に地番入力フォームを開く
- **「🗺 地図タップで立てる」**: タップ待機モードへ → 地図を1回タップ → その位置で地番入力フォーム
- 入力項目: **地番**（必須・市区町村から）、**担当者**（初期値: ログイン中ユーザー）、**メモ**
- 保存形式（既存スキーマに追加フィールド）:
  ```js
  {
    id, address, lat, lng, assignee, memo,
    status: "未訪問",
    dm: "未", visit: "未",
    coordsManual: true,   // 🆕 ジオコーディング除外フラグ
    source: "現地ピン",    // 🆕 識別用
    createdAt, updatedAt,
    history: [], visitLog: [], family: [],
  }
  ```
- **`runGeocoding` を改修**: `if (j.coordsManual) return false` で現地ピンを対象外に
- **CSV エクスポート**: 「＋」メニューに「📥 現地ピンCSV出力」追加（`genchi_pin_YYYY-MM-DD.csv`）
- 列: ID / 作成日 / 地番 / 担当者 / 緯度 / 経度 / ステータス / メモ

#### 2) 現在地表示（v8.95）

- `navigator.geolocation.watchPosition` で継続取得
- 地図上に青点（中心16px）＋ 誤差サークル（精度の半径）
- **「🧭 現在地へ」ボタン**: 地図を自分の位置にセンタリング
- **viewMode が "map" 以外になったら自動で `clearWatch`**（バッテリー配慮）
- 拒否/失敗時はエラーメッセージを赤字表示

#### 3) 地図UX改善（v8.96）

- **高さ拡大**: `height={420}` → `height="65vh"`（画面の65%）
- **ズーム/位置維持**: `hasInitializedBoundsRef` で `fitBounds` を初回のみに制限。以降ユーザーがズーム/パンしても自動リセットしない
- **「🎯 全件表示」ボタン**: 手動で全ピン収まる位置に戻したいとき用

### 変更したコード箇所

- `LeafletMap` コンポーネント（line ~3386）
  - 新prop: `onMapClick`, `currentLocation`, `centerOnLocationKey`, `fitBoundsKey`
  - 新ref: `currentLocMarkerRef`, `currentLocCircleRef`, `hasInitializedBoundsRef`
  - 新useEffect 4つ: 地図タップ、現在地マーカー、現在地センタリング、手動 fitBounds
- `runGeocoding`（line ~11940）に `coordsManual` ガードを追加
- `JiagePage`（function 開始 line ~11167）に state・useEffect・ハンドラ多数追加
- `JiagePage` の地図ビュー JSX に操作パネル、`LeafletMap` の prop 拡張、ピン入力モーダル
- `＋`メニューに CSV 出力ボタン追加

---

## 🛡️ 重要な制約・安全規則（必読）

過去に v8.80 でデモデータと実データの取り違えにより本番データが消えた事故あり。以下を厳守:

1. **Supabaseへの書き込み前に必ずバックアップを取る**（`backup.yml` を手動実行可能）
2. **既存データの構造を破壊する移行スクリプトを書かない**。スキーマ追加は OK、フィールド削除/リネームは要慎重
3. **APP_VERSION の bump は必須**（変更が伝搬しない／更新バナーが出ない）
4. **`runGeocoding` の対象から `coordsManual: true` を除外**（実測座標を上書きしない）
5. **インポート時のマージ仕様を維持**: 「物件住所＋所有者で重複判定」「DM・住確・メモは空/未では上書きしない」（v8.91 で実装済み）
6. **同期ロジックを変更する時は `tombstones` / `_fieldUpdatedAt` / `protectedKeys` の関係を理解した上で**（v8.73-v8.89 の長い修正履歴あり）

### 同期の仕組み（概略）

- 配列フィールド（`stocks`, `jiage`, `approaches`, `mediations`, etc.）はアイテム単位で `mergeItems()` でマージ
- 上位アイテムの削除は **top-level `data.tombstones.{key}.{id}: timestamp`** で確定。30日間保持
- ネスト配列（`viewings`, `visitLog`, `photos`, `family`）は親アイテムごとの `{nested}Tombstones` で削除確定
- v8.86 以降: `data.adminMembersUpdatedAt` のような field-level 更新時刻で arbitration（特定キー）
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
// 地上げステータス（line ~414）
const ATTACK_STATUSES = ["未訪問","初訪","再訪","見込み","中長期見込","見込無し","交渉中","媒介","仕入"];

// 地上げステータスの色（v8.87 で追加）
const JIAGE_STATUS_COLORS = {
  "未訪問": "#94a3b8", "初訪": "#0ea5e9", "再訪": "#2563eb",
  "見込み": "#22c55e", "中長期見込": "#fbbf24", "見込無し": "#ef4444",
  "交渉中": "#f97316", "媒介": "#a855f7", "仕入": "#06b6d4",
};

// 地上げ訪問結果
const VISIT_RESULTS = [
  { key: "home",     label: "🤝 面談",     ... autoStatus: "初訪" },
  { key: "ignore",   label: "🚪 居留守",   ... autoStatus: "初訪" },
  { key: "absent",   label: "🚫 不在",     ... autoStatus: "初訪" },
  { key: "rejected", label: "⛔ 訪問禁止", ... autoStatus: "初訪" },
];

// 在庫ステータス
const STOCK_STATUSES = ["仕入役調中","仕契準備中","仕契完了","仕決完了",
  "登記依頼完了","残置物処理中","リフォーム待ち","リフォーム中","リフォーム完了",
  "販売中","売契準備中","売却役調中","売契完了","売決完了"];

// メンバー
const MEMBERS = ["たっくん","長島","松村","脇本","谷津","下田","比嘉","比嘉・下田"];

// 管理者（v8.86 で複数対応）
data.adminMembers = ["下田", "比嘉"];  // 配列
data.adminMember = "下田";              // 後方互換の単数
data.adminMembersUpdatedAt = <ts>;     // v8.89 端末跨ぎ同期用
```

---

## 📜 直近のバージョン履歴

| ver | 主な変更 |
|---|---|
| v8.86 | 複数管理者対応（下田＋比嘉） |
| v8.87 | 地上げのステータス色分け・NG物件の赤枠 |
| v8.88 | 地上げカード全体の枠もステータス色 |
| v8.89 | 管理者リストの端末跨ぎ同期バグ修正（field-level updatedAt） |
| v8.90 | Claude Code: APP_VERSION bump |
| v8.91 | Claude Code: 取込時のDM・住確を「空/未」では上書きしない |
| v8.92 | Babelコンパイル結果を localStorage にキャッシュ |
| v8.93 | UX 4種（月切替バッジ・決済日アラート・反響顧客名検索×2） |
| v8.94 | 自動バックアップワークフロー追加＋ APP_VERSION |
| Phase 3 | ビルドパイプライン導入。GitHub Pages の Source を「GitHub Actions」に切替 |
| **v8.95** | **地上げ地図: 現地ピン（手動座標）＋現在地表示＋CSVエクスポート** |
| **v8.96** | **地図高さ拡大・ズーム保持・全件表示ボタン** |

---

## 🚧 未着手の改善案（優先度順）

### Phase 4: コード分割（保守性向上）

`index.html` の 16,000 行を機能ごとに分割:
- `src/components/` （共通コンポーネント: Tag, MemberTag, StatusTag, LeafletMap, BottomSheet など）
- `src/pages/` （Dashboard, StockPage, ApproachPage, JiagePage, MorePage など）
- `src/lib/` （データマージ、ジオコーディング、Supabase 通信、tombstone 管理など）
- `tools/build.mjs` を拡張して、bundle 化して HTML に埋め込む
- 段階的に進める（1機能=1コミット）こと

### 業務に効く機能追加（ユーザーと議論済）

1. **ホーム画面に「自分の今日のToDo」枠**: 今日の訪問予定、期限切れ、入力漏れを一覧
2. **グローバル検索**: タブをまたいだ全文検索
3. **データ完全性ダッシュボード**: 売契完了で売決日空 / 仕契完了で仕決日空 などを横断検知
4. **エクスポート機能**: 在庫・地上げ・反響・積算を Excel/CSV で出力
5. **物件のシェアリンク**: `?stock=123` 形式の直リンク
6. **@メンション機能**: コメントに `@比嘉` でプッシュ通知
7. **写真の GPS 情報利用**: EXIF から位置自動抽出
8. **操作履歴（監査ログ）**: 削除や決済日変更などの重要操作の記録強化
9. **2要素認証**: 4桁パスワード補強
10. **ゴミ箱機能**: 30日以内なら復元可能

### 残ポンディング項目（古い）

- #86: 予定カードの反響イベントに「詳細」ボタン追加（v8.60 で多分対応済みだが要確認）

---

## 🔑 こまかいけど重要なこと

### Supabase 認証情報

`index.html` の上部に直書きされている:
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

### 現地ピン CSV 出力後の後工程（ユーザーの業務）

ユーザーは、現地ピンを CSV で出力したあと、地番を使って**登記簿（謄本）を一括取得する自動処理**を別途回す予定。なので CSV の「地番」列は正確である必要がある（入力時のテキストそのまま）。

### 過去事故の記録（必読）

- **v8.80 事故**: デモデータ削除のつもりが、デモ名と同じ名前のついた本物の在庫データを削除してしまった。tombstone と Supabase の競合により他端末で復活も困難に。教訓: **「○○という名前を含む」のような broad な削除ロジックは絶対書かない**
- **v8.86 → v8.89 の管理者同期バグ**: protectedKeys に adminMembers を入れたせいで、他端末で行った管理者追加が反映されなくなった。教訓: **「直近5分編集ガード」は強力すぎるので field-level updatedAt に置き換えるべき**

---

## 🤝 引き継ぎコメント

このセッションで以下を一気にやりました:
- 過去事故（v8.80）のデータ調査と原因特定
- v8.86–v8.96 の機能追加・バグ修正
- ビルドパイプラインと本番デプロイ切替（Phase 3 完了）
- 自動バックアップ仕組みの構築
- 現地ピン機能（v8.95）と地図UX改善（v8.96）

Phase 4（コード分割）に手を付ければ、保守性が劇的に上がります。が、慎重に。各機能を別ファイルに切り出すたびに preview-build で artifact 検証 → ブラウザで動作確認 → 問題なければ commit、というサイクルを守ってください。

何かあれば、`backups/` フォルダの自動バックアップから復元できます。
