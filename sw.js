// ひかり不動産 PWA Service Worker（Web Push 対応版）
const CACHE_VERSION = 'hikari-app-v4-2026-05-12';

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

// 通知をクリックしたらアプリを開く
self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientsArr => {
      const existingClient = clientsArr.find(c => c.url.includes('hikari-app'));
      if (existingClient) return existingClient.focus();
      return self.clients.openWindow('./');
    })
  );
});

// メインスレッドからのメッセージで通知を表示（アプリ開いてる時用）
self.addEventListener('message', e => {
  if (e.data && e.data.type === 'SHOW_NOTIFICATION') {
    const { title, body, tag, icon } = e.data;
    self.registration.showNotification(title, {
      body,
      tag: tag || 'hikari-event',
      icon: icon || './icon-192.png',
      badge: icon || './icon-192.png',
      vibrate: [200, 100, 200],
      requireInteraction: false,
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
    tag: data.tag || `hikari-push-${Date.now()}`,
    icon: data.icon || './icon-192.png',
    badge: './icon-192.png',
    vibrate: [200, 100, 200, 100, 200],
    requireInteraction: data.requireInteraction || false,
    data: data.data || {},
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
