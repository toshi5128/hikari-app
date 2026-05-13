// ひかり不動産 PWA Service Worker（Web Push + 通知タップ画面遷移 + 全タグパターン対応 v10）
const CACHE_VERSION = 'hikari-app-v10-2026-05-14';

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

function parseTagToNav(tag) {
  if (!tag || typeof tag !== 'string') return null;

  let m = tag.match(/^hikari-business-start-(.+)-(\d{4}-\d{2}-\d{2})$/);
  if (m) return { tab: 'approach', sub: 'input', member: m[1], date: m[2] };

  m = tag.match(/^hikari-business-close-(.+)-(\d{4}-\d{2}-\d{2})$/);
  if (m) return { tab: 'approach', sub: 'input', member: m[1], date: m[2] };

  m = tag.match(/^hikari-comment-(.+)-(\d{4}-\d{2}-\d{2})-\d+$/);
  if (m) return { tab: 'approach', sub: 'input', member: m[1], date: m[2], scrollTo: 'comments' };

  m = tag.match(/^hikari-goal-(.+)-\d+$/);
  if (m) return { tab: 'approach', sub: 'goals' };

  m = tag.match(/^hikari-stock-[a-z-]+-(\d+)/);
  if (m) return { tab: 'stock', stockLinkId: m[1] };

  m = tag.match(/^hikari-sekisan-result-(\d+)$/);
  if (m) return { tab: 'dashboard', sekisanLinkId: m[1] };

  m = tag.match(/^hikari-new-event-(\d+)$/);
  if (m) return { tab: 'dashboard', eventId: m[1] };

  // 🆕 v10 汎用パターン: hikari-<target>-<action>-<itemId>
  m = tag.match(/^hikari-(stock|jiage|owner|sekisan|yakusho|event)-(add|update|delete|promote|import)-(\d+)$/);
  if (m) {
    const target = m[1];
    const itemId = m[3];
    const tabMap = {
      stock: { tab: 'stock', linkKey: 'stockLinkId' },
      jiage: { tab: 'jiage', linkKey: 'jiageLinkId' },
      owner: { tab: 'jiage', linkKey: 'ownerLinkId' },
      sekisan: { tab: 'approach', sub: 'cases', linkKey: 'sekisanLinkId' },
      yakusho: { tab: 'dashboard', linkKey: 'yakushoLinkId' },
      event: { tab: 'dashboard', linkKey: 'eventId' },
    };
    const info = tabMap[target];
    if (info) {
      const nav = { tab: info.tab };
      if (info.sub) nav.sub = info.sub;
      nav[info.linkKey] = itemId;
      return nav;
    }
  }

  return null;
}

function extractNavData(payload) {
  if (!payload) return {};
  if (payload.data && (payload.data.tab || payload.data.member || payload.data.stockLinkId || payload.data.sekisanLinkId || payload.data.jiageLinkId || payload.data.ownerLinkId || payload.data.yakushoLinkId || payload.data.eventId)) {
    return payload.data;
  }
  if (payload.tab || payload.member || payload.stockLinkId || payload.sekisanLinkId || payload.jiageLinkId || payload.ownerLinkId || payload.yakushoLinkId || payload.eventId) {
    return {
      tab: payload.tab, sub: payload.sub, member: payload.member, date: payload.date,
      scrollTo: payload.scrollTo,
      stockLinkId: payload.stockLinkId, sekisanLinkId: payload.sekisanLinkId,
      jiageLinkId: payload.jiageLinkId, ownerLinkId: payload.ownerLinkId,
      yakushoLinkId: payload.yakushoLinkId, eventId: payload.eventId,
    };
  }
  const fromTag = parseTagToNav(payload.tag);
  if (fromTag) return fromTag;
  return {};
}

self.addEventListener('push', event => {
  let payload = {};
  try {
    payload = event.data?.json() || {};
  } catch (e) {
    payload = { title: event.data?.text() || '通知', body: '' };
  }

  const navData = extractNavData(payload);
  console.log('[SW v10] Push received:', payload, '→ navData:', navData);

  const title = payload.title || 'ひかり不動産';
  const options = {
    body: payload.body || '',
    icon: payload.icon || './icon-192.png',
    badge: payload.badge || './icon-192.png',
    tag: payload.tag,
    data: navData,
    requireInteraction: false,
    vibrate: [200, 100, 200],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const nav = event.notification.data || {};
  console.log('[SW v10] Notification clicked, nav:', nav);

  event.waitUntil((async () => {
    const allClients = await self.clients.matchAll({
      type: 'window', includeUncontrolled: true,
    });

    for (const client of allClients) {
      if ('focus' in client) {
        await client.focus();
        try { client.postMessage({ type: 'NAVIGATE', data: nav }); } catch (e) {}
        return;
      }
    }

    if (self.clients.openWindow) {
      const params = new URLSearchParams();
      if (nav.tab) params.set('tab', nav.tab);
      if (nav.sub) params.set('sub', nav.sub);
      if (nav.member) params.set('member', nav.member);
      if (nav.date) params.set('date', nav.date);
      if (nav.scrollTo) params.set('scrollTo', nav.scrollTo);
      if (nav.stockLinkId) params.set('stockLinkId', nav.stockLinkId);
      if (nav.sekisanLinkId) params.set('sekisanLinkId', nav.sekisanLinkId);
      if (nav.jiageLinkId) params.set('jiageLinkId', nav.jiageLinkId);
      if (nav.ownerLinkId) params.set('ownerLinkId', nav.ownerLinkId);
      if (nav.yakushoLinkId) params.set('yakushoLinkId', nav.yakushoLinkId);
      if (nav.eventId) params.set('eventId', nav.eventId);
      const qs = params.toString();
      return self.clients.openWindow(qs ? `./?${qs}` : './');
    }
  })());
});

self.addEventListener('message', event => {
  if (event.data?.type === 'SHOW_NOTIFICATION') {
    const { title, body, tag } = event.data;
    self.registration.showNotification(title || '通知', {
      body: body || '', tag: tag || 'in-page-test',
      icon: './icon-192.png', badge: './icon-192.png',
    });
  }
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
