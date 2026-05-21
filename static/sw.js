const CACHE = 'eduvia-v3';

self.addEventListener('install', e => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(clients.claim());
});

self.addEventListener('push', e => {
  const data = e.data ? e.data.json() : {};
  const title = data.title || 'Eduvia AI';
  const options = {
    body: data.body || 'Czas na naukę! 🎓',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    vibrate: [100, 50, 100],
    data: { url: data.url || '/dashboard_FINAL.html' },
    actions: [
      { action: 'open', title: '📚 Ucz się teraz' },
      { action: 'close', title: 'Później' }
    ]
  };
  e.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  if (e.action === 'close') return;
  const url = e.notification.data?.url || '/dashboard_FINAL.html';
  e.waitUntil(clients.matchAll({ type: 'window' }).then(list => {
    for (const client of list) {
      if (client.url.includes(url) && 'focus' in client) return client.focus();
    }
    if (clients.openWindow) return clients.openWindow(url);
  }));
});
