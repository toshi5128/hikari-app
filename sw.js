// ひかり不動産 PWA Service Worker
const CACHE_VERSION = 'hikari-app-v3-2026-05-11';

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

// メインスレッドからのメッセージで通知を表示
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

// fetchはパススルー（キャッシュしないでブラウザ標準にまかせる）
self.addEventListener('fetch', e => {
  // パススルー
});
