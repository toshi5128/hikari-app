// =============================================================
// ひかり不動産 一斉送信ツール ── アプリからの送信窓口（doPost）
//
// 使い方：
//   1. スプレッドシート「一斉送信」の Apps Script にこの中身を追記して保存
//   2. デプロイ → 新しいデプロイ → 種類「ウェブアプリ」
//        次のユーザーとして実行 : 自分
//        アクセスできるユーザー   : 全員
//   3. 発行された /exec の URL を、アプリの
//      「その他 → 先行打診 → 送信の設定」に貼る
//   4. 合言葉（API_TOKEN）も同じ画面に貼る
//
// 送信元は「デプロイした人のGoogleアカウント」。
// 差出人の表示名・返信先は「担当者」シートの行を使う。
// =============================================================

var API_TOKEN = 'hikari-sakidashi-2026';

function doGet() {
  return _jsonOut({ ok: true, msg: 'hikari mail api' });
}

function doPost(e) {
  var res;
  try {
    var p = JSON.parse(e.postData.contents);
    if (String(p.token || '') !== API_TOKEN) throw new Error('合言葉が違います');

    var st = _apiSender();
    var list = p.to || [];
    if (!list.length) throw new Error('宛先がありません');

    var quota = MailApp.getRemainingDailyQuota();
    var sent = 0, failed = 0, errors = [];
    var ctx = { prop: p.property || '', price: p.priceText || '', doc: p.docUrl || '' };

    for (var i = 0; i < list.length; i++) {
      if (sent >= quota) { errors.push('本日の送信上限に達したため中断'); break; }
      var r = list[i] || {};
      if (!r.email) { failed++; continue; }
      try {
        var subject = _apiFill(p.subject, r, ctx);
        var body = _apiFill(p.body, r, ctx);
        if (st.sign) body = body + '\n\n' + st.sign;
        GmailApp.sendEmail(r.email, subject, body, _apiOpts(st));
        sent++;
      } catch (err) {
        failed++;
        errors.push(String(r.email) + ' : ' + err.message);
      }
      Utilities.sleep(300);
    }
    _apiLog(p, sent, failed);
    res = { ok: true, sent: sent, failed: failed, errors: errors, quotaLeft: MailApp.getRemainingDailyQuota() };
  } catch (e2) {
    res = { ok: false, error: String((e2 && e2.message) || e2) };
  }
  return _jsonOut(res);
}

function _jsonOut(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// 差出人（担当者シートの1行目＝既定の送り手を使う。fromAlias があればそれを名乗る）
function _apiSender() {
  var sh = ensureStaffSheet_();
  var last = sh.getLastRow();
  var rows = (last >= 2) ? sh.getRange(2, 1, last - 1, 5).getValues() : [];
  var me = myEmail_();
  var hit = null;
  for (var i = 0; i < rows.length; i++) {
    var m = String(rows[i][0]).trim();
    if (m && m.toLowerCase() === me) { hit = rows[i]; break; }
  }
  if (!hit && rows.length) hit = rows[0];
  if (!hit) return { mail: '', name: CFG.senderName, sign: '' };
  return { mail: String(hit[0]).trim(), name: String(hit[1]).trim(), sign: String(hit[4] || '') };
}

function _apiOpts(st) {
  var o = { name: st.name || CFG.senderName, replyTo: st.mail || CFG.replyTo };
  if (CFG.fromAlias && canUseAlias_()) { o.from = CFG.fromAlias; o.replyTo = CFG.fromAlias; }
  if (CFG.fromAliasName) o.name = CFG.fromAliasName;
  return o;
}

function _apiFill(text, r, ctx) {
  var company = String(r.company || '').trim();
  var person = String(r.name || '').trim();
  var atena = company
    ? (person ? company + '\n' + person + ' 様' : company + ' ご担当者様')
    : (person ? person + ' 様' : 'ご担当者様');
  return String(text || '')
    .replace(/\{\{宛名\}\}/g, atena)
    .replace(/\{\{会社名\}\}/g, company)
    .replace(/\{\{担当者\}\}/g, person || 'ご担当者')
    .replace(/\{\{物件名\}\}/g, ctx.prop)
    .replace(/\{\{価格\}\}/g, ctx.price)
    .replace(/\{\{資料URL\}\}/g, ctx.doc || '（資料は追ってお送りします）');
}

// 送信ログを「打診ログ」シートに1行残す
function _apiLog(p, sent, failed) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sh = ss.getSheetByName('打診ログ');
    if (!sh) {
      sh = ss.insertSheet('打診ログ');
      sh.getRange(1, 1, 1, 6).setValues([['日時', '物件', '件名', '送信', '失敗', '資料URL']]);
      sh.getRange(1, 1, 1, 6).setFontWeight('bold').setBackground('#d9ead3');
      sh.setFrozenRows(1);
    }
    sh.appendRow([nowStr_(), p.property || '', p.subject || '', sent, failed, p.docUrl || '']);
  } catch (e) { /* ログ失敗は本処理に影響させない */ }
}
