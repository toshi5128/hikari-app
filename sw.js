// ひかり不動産 PWA Service Worker
const CACHE_NAME = 'hikari-app-v1';

self.addEventListener('install', e => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(self.clients.claim());
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

// メインスレッドからのメッセージで通知を表示（バックグラウンドでも動く）
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
});

// オフライン時の最低限のフォールバック（無くてもOK）
self.addEventListener('fetch', e => {
  // パススルー（オフライン対応は今回は最小限）
});
