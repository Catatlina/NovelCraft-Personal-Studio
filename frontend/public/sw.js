/* eslint-disable */
// PWA Service Worker — offline cache
const CACHE = "novelcraft-v1";
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(["/","/index.html"])));
  self.skipWaiting();
});
self.addEventListener("fetch", (e) => {
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).catch(() => new Response("离线模式"))));
});
