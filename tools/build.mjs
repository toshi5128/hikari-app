// 🏗️ ひかり不動産: ビルドスクリプト（事前コンパイル版を生成）
//
// やること:
//   1. index.html を読む
//   2. <script type="text/plain" id="hikari-jsx-src">...</script> から JSX を取り出す
//   3. Babel preset-react で事前コンパイル
//   4. v8.92 のキャッシュローダーを削除（事前コンパイルなので不要）
//   5. JSX <script> を実行可能な <script> に置換（コンパイル済みコードを inline）
//   6. Babel-standalone の参照も削除（既にコンパイル済みなのでランタイム Babel 不要）
//   7. 出来上がりを dist/index.html に保存
//
// 結果:
//   ・初回起動も2回目以降も同じ速度（コンパイル不要）
//   ・全端末で爆速（Android低スペックでも即起動）
//   ・Babel-standalone (3MB) の読み込みが不要

import { readFileSync, writeFileSync, mkdirSync, statSync, copyFileSync, existsSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import babel from "@babel/core";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const SRC = join(ROOT, "index.html");
const DIST_DIR = join(ROOT, "dist");
const DIST = join(DIST_DIR, "index.html");

console.log(`\n=== 🏗️ ひかり不動産 ビルド ===`);
console.log(`入力: ${SRC}`);

const html = readFileSync(SRC, "utf-8");
console.log(`元 HTML サイズ: ${(html.length / 1024).toFixed(1)} KB`);

// JSX 抽出
const jsxMatch = html.match(
  /<script type="text\/plain" id="hikari-jsx-src">([\s\S]*?)<\/script>/
);
if (!jsxMatch) {
  console.error(
    'ERROR: <script type="text/plain" id="hikari-jsx-src"> が見つかりません'
  );
  console.error("index.html が v8.92 以降の構造になっていることを確認してください");
  process.exit(1);
}
const jsx = jsxMatch[1];
console.log(`JSX サイズ: ${(jsx.length / 1024).toFixed(1)} KB`);

// Babel コンパイル
console.log(`Babel コンパイル中...`);
const t0 = Date.now();
const result = babel.transformSync(jsx, {
  presets: [["@babel/preset-react", {}]],
  compact: true,
  comments: false,
  babelrc: false,
  configFile: false,
});
const dt = Date.now() - t0;
if (!result || !result.code) {
  console.error("ERROR: Babel コンパイルが失敗しました");
  process.exit(1);
}
const compiled = result.code;
console.log(`コンパイル完了: ${dt}ms (出力 ${(compiled.length / 1024).toFixed(1)} KB)`);

let built = html;

// 1) v8.92 キャッシュローダーの削除
const loaderRegex =
  /\n*<!-- 🆕 v8\.92: Babel コンパイル結果キャッシュ・ローダー[\s\S]*?\<\/script>\n/;
if (loaderRegex.test(built)) {
  built = built.replace(loaderRegex, "\n");
  console.log("✓ v8.92 キャッシュローダーを削除");
} else {
  console.log("- v8.92 ローダーは見つからず（OK: 古い版か、既に置換済み）");
}

// 2) JSX <script type="text/plain"> を実行可能な <script> に置換
built = built.replace(
  /<script type="text\/plain" id="hikari-jsx-src">[\s\S]*?<\/script>/,
  `<!-- 🏗️ ビルド済み: 事前コンパイル済み JS (Babel ランタイム不要) -->\n<script>${compiled}</script>`
);
console.log("✓ JSX を事前コンパイル済み JS に置換");

// 3) v8.92 の説明コメントも掃除
built = built.replace(
  /<!-- 🆕 v8\.92: Babel-standalone はキャッシュミス時のみ動的読み込み[^>]*-->\n*/,
  ""
);

// dist フォルダに保存
mkdirSync(DIST_DIR, { recursive: true });
writeFileSync(DIST, built);

// 🆕 v8.94: PWA で必要な静的アセットも dist/ にコピー（本番デプロイ用）
const STATIC_ASSETS = ["manifest.json", "sw.js", "icon-192.png", "icon-512.png"];
let copiedCount = 0;
for (const f of STATIC_ASSETS) {
  const src = join(ROOT, f);
  const dst = join(DIST_DIR, f);
  if (existsSync(src)) {
    copyFileSync(src, dst);
    copiedCount++;
  } else {
    console.warn(`⚠️  ${f} が見つからない（スキップ）`);
  }
}

console.log(`\n=== 完了 ===`);
console.log(`出力: ${DIST}`);
console.log(`出力サイズ: ${(built.length / 1024).toFixed(1)} KB`);
console.log(`削減率（元比）: ${((built.length / html.length) * 100).toFixed(1)}%`);
console.log(`静的アセットコピー: ${copiedCount}/${STATIC_ASSETS.length}`);
console.log(
  `\n💡 動作確認: dist/index.html をブラウザで直接開いて、今と同じように動くか確認してください\n`
);
