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
  e.notificati
