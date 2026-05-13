// ひかり不動産 PWA Service Worker（Web Push + 通知タップ画面遷移 + タグfallback）
const CACHE_VERSION = 'hikari-app-v8-2026-05-13';

self.addEventListener('install', e => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames
        .filter(name => name !== CACHE_VERSION)
        .map(name => caches.delete(name))
    );
    await self.clients.claim();
  })());
});

// 通知の tag 文字列から飛び先情報を抽出（Edge Function が data を落とした場合の保険）
function parseTagToNav(tag) {
  if (!tag || typeof tag !== 'string') return null;

  // パターン①: hikari-business-start-<member>-<YYYY-MM-DD>
  let m = tag.match(/^hikari-business-start-(.+)-(\d{4}-\d{2}-\d{2})$/);
  if (m) {
    return { tab: 'approach', sub: 'input', member: m[1], date: m[2] };
  }
  // パターン②: hikari-business-close-<member>-<YYYY-MM-DD>
  m = tag.match(/^hikari-business-close-(.+)-(\d{4}-\d{2}-\d{2})$/);
  if (m) {
    return { tab: 'approach', sub: 'input', member: m[1], date: m[2] };
  }
  // パターン③: hikari-comment-<member>-<YYYY-MM-DD>-<commentId>
  m = tag.match(/^hikari-comment-(.+)-(\d{4}-\d{2}-\d{2})-\d+$/);
  if (m) {
    return { tab: 'approach', sub: 'input', member: m[1], date: m[2], scrollTo: 'comments' };
  }
  return null;
}

// payload から「飛び先情報」を抽出（nested / flat / tag fallback の3段階）
function extractNavData(payload) {
  if (!payload) return {};
  // ① nested: payload.data.tab
  if (payload.data && (payload.data.tab || payload.data.member)) {
    return payload.data;
  }
  // ② flat: payload.tab
  if (payload.tab || payload.member) {
    return {
      tab: payload.tab,
      sub: payload.sub,
      member: payload.member,
      date: payload.date,
      scrollTo: payload.scrollTo,
    };
  }
  // ③ タグから推測（最後の保険）
  if (payload.tag) {
    const navFromTag = parseTagToNav(payload.tag);
    if (navFromTag) {
      console.log('[SW] tagから飛び先情報を復元:', JSON.stringify(navFromTag));
      return navFromTag;
    }
  }
  return {};
}

// 🔔 通知をクリック：既存タブにメッセージ送りつつフォーカス / 無ければクエリ付きで新規ウィンドウ
self.addEventListener('notificationclick', e => {
  e.notification.close();
  let navData = e.notification.data || {};

  // notification.data が空でも tag から復元できないか試す
  if ((!navData || Object.keys(navData).length === 0) && e.notification.tag) {
    const fromTag = parseTagToNav(e.notification.tag);
    if (fromTag) {
      navData = fromTag;
      console.log('[SW] notificationclick: tagから navData 復元:', JSON.stringify(navData));
    }
  }

  console.log('[SW] notificationclick 最終 navData:', JSON.stringify(navData));

  const buildQuery = (d) => {
    const keys = Object.keys(d || {}).filter(k => d[k] != null && d[k] !== '');
    if (keys.length === 0) return '';
    return '?' + keys.map(k => encodeURIComponent(k) + '=' + encodeURIComponent(d[k])).join('&');
  };

  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientsArr => {
      const existingClient = clientsArr.find(c => c.url.includes('hikari-app'));
      if (existingClient) {
        try { existingClient.postMessage({ type: 'NAVIGATE', data: navData }); } catch (err) {}
        return existingClient.focus();
      }
      return self.clients.openWindow('./' + buildQuery(navData));
    })
  );
});

// メインスレッドからのメッセージで通知を表示（アプリ開いてる時用）
self.addEventListener('message', e => {
  if (e.data && e.data.type === 'SHOW_NOTIFICATION') {
    const { title, body, tag, icon, data } = e.data;
    self.registration.showNotification(title, {
      body,
      tag: tag || 'hikari-event',
      icon: icon || './icon-192.png',
      badge: icon || './icon-192.png',
      vibrate: [200, 100, 200],
      requireInteraction: false,
      data: data || {},
    });
  }
  if (e.data && e.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// ★ Web Push 受信 ★
self.addEventListener('push', event => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (e) {
    payload = { title: 'ひかり不動産', body: event.data ? event.data.text() : '新しい通知' };
  }

  console.log('[SW] push received payload:', JSON.stringify(payload));

  // 飛び先情報を柔軟に抽出（nested / flat / tag fallback）
  const navData = extractNavData(payload);

  console.log('[SW] extracted navData:', JSON.stringify(navData));

  const title = payload.title || '📅 ひかり不動産';
  const options = {
    body: payload.body || '',
    tag: payload.tag || ('hikari-push-' + Date.now()),
    icon: payload.icon || './icon-192.png',
    badge: './icon-192.png',
    vibrate: [200, 100, 200, 100, 200],
    requireInteraction: payload.requireInteraction || false,
    data: navData, // ← 通知タップ時に使われる飛び先情報
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// 購読状態変化時の再購読依頼
self.addEventListener('pushsubscriptionchange', event => {
  event.waitUntil(
    self.clients.matchAll().then(clients => {
      clients.forEach(c => c.postMessage({ type: 'RESUBSCRIBE_PUSH' }));
    })
  );
});

self.addEventListener('fetch', e => {
  // パススルー
});
