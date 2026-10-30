const CACHE_NAME = 'hope-chiffrage-shell-v26';
const SHELL_URLS = [
  '/m/chiffrage/',
  '/static/chiffrage_mobile/app.js',
  '/static/chiffrage_mobile/styles.css',
  '/static/chiffrage_mobile/manifest.webmanifest',
  '/static/chiffrage_mobile/icons/icon-192.png',
  '/static/chiffrage_mobile/icons/icon-512.png',
  '/static/chiffrage_mobile/logo-new.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Jamais de cache pour l'API — toujours des données fraîches, ou un échec explicite
  // géré côté app.js (bannière hors-ligne) plutôt qu'une réponse mensongère.
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});

self.addEventListener('push', (event) => {
  let payload = { title: 'HOPE — Chiffrage', body: 'Nouvelle notification.', url: '/m/chiffrage/' };
  if (event.data) {
    try { payload = { ...payload, ...event.data.json() }; } catch (e) { payload.body = event.data.text(); }
  }
  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: '/static/chiffrage_mobile/icons/icon-192.png',
      badge: '/static/chiffrage_mobile/icons/icon-192.png',
      vibrate: [200, 100, 200],
      tag: payload.url,
      renotify: true,
      timestamp: Date.now(),
      data: { url: payload.url },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data && event.notification.data.url ? event.notification.data.url : '/m/chiffrage/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes('/m/chiffrage/') && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});
