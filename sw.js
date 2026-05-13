// ひかり不動産 PWA Service Worker（Web Push + 通知タップ画面遷移 対応版）
const CACHE_VERSION = 'hikari-app-v7-2026-05-13';

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

// payload から「飛び先情報」を取り出す共通関数（nested / flat / フォールバック対応）
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
    };
  }
  return {};
}

// 🔔 通知をクリック：既存タブにメッセージ送りつつフォーカス / 無ければクエリ付きで新規ウィンドウ
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const navData = e.notification.data || {};

  console.log('[SW] notificationclick navData:', JSON.stringify(navData));

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

  // 飛び先情報を柔軟に抽出（nested / flat 両対応）
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

// fetchはパススルー
self.addEventListener('fetch', e => {
  // パススルー
});
