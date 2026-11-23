const CACHE_NAME = 'studyx-static-calendar-task-v7';
const STATIC_ASSETS = [
  '/static/css/studyx.css',
  '/static/css/studyx-layout.css',
  '/static/css/studyx-pages.css',
  '/static/css/studyx-components.css',
  '/static/css/studyx-progress.css',
  '/static/css/studyx-mobile.css',
  '/static/css/studyx-fixes.css',
  '/static/js/studyx.js',
  '/static/img/studyx-mark.svg',
  '/static/manifest.webmanifest',
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith('studyx-') && key !== CACHE_NAME).map(key => caches.delete(key))
  )));
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || !url.pathname.startsWith('/static/')) return;
  event.respondWith(caches.match(request).then(cached => {
    const fresh = fetch(request).then(response => {
      if (response.ok) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(request, copy)).catch(() => {});
      }
      return response;
    });
    return fresh.catch(() => cached || Response.error());
  }));
});
