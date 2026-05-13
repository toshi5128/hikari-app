// ひかり不動産 PWA Service Worker（Web Push + 通知タップ画面遷移 対応版）
const CACHE_VERSION = 'hikari-app-v6-2026-05-13';

self.addEventListener('install', e => {
  // 新しい SW はすぐにアクティブにする
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    // 古いキャッシュを全削除
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames
        .filter(name => name !== CACHE_VERSION)
        .map(name => caches.delete(name))
    );
    // すべての開いているクライアントをこの SW の制御下に置く
    await self.clients.claim();
  })());
});

// 🔔 通知をクリックした時：既存タブがあれば NAVIGATE メッセージを送ってフォーカス、無ければクエリ付きで新規ウィンドウを開く
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const navData = e.notification.data || {};

  // クエリ文字列を組み立て（新規ウィンドウ用）
  const buildQuery = (d) => {
    const keys = Object.keys(d || {}).filter(k => d[k] != null && d[k] !== '');
    if (keys.length === 0) return '';
    return '?' + keys.map(k => encodeURIComponent(k) + '=' + encodeURIComponent(d[k])).join('&');
  };

  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientsArr => {
      const existingClient = clientsArr.find(c => c.url.includes('hikari-app'));
      if (existingClient) {
        // 既存タブにメッセージを送って画面遷移を依頼 → タブをフォーカス
        try { existingClient.postMessage({ type: 'NAVIGATE', data: navData }); } catch (err) {}
        return existingClient.focus();
      }
      // 新規ウィンドウをクエリ付きで開く
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

// ★ Web Push 受信（アプリ閉じてても届く！） ★
self.addEventListener('push', event => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: 'ひかり不動産', body: event.data ? event.data.text() : '新しい通知があります' };
  }
  const title = data.title || '📅 ひかり不動産';
  const options = {
    body: data.body || '',
    tag: data.tag || ('hikari-push-' + Date.now()),
    icon: data.icon || './icon-192.png',
    badge: './icon-192.png',
    vibrate: [200, 100, 200, 100, 200],
    requireInteraction: data.requireInteraction || false,
    data: data.data || {}, // ← 通知タップ時に渡される飛び先情報
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// プッシュ通知の購読状態が変わったら（端末再起動など）再購読する
self.addEventListener('pushsubscriptionchange', event => {
  event.waitUntil(
    self.clients.matchAll().then(clients => {
      clients.forEach(c => c.postMessage({ type: 'RESUBSCRIBE_PUSH' }));
    })
  );
});

// fetchはパススルー（キャッシュしないでブラウザ標準にまかせる）
self.addEventListener('fetch', e => {
  // パススルー
});
