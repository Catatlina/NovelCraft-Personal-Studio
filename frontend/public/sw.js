/* eslint-disable */
// PWA Service Worker — network-first, v4
const CACHE = "novelcraft-v4";
self.addEventListener("install", (e) => {
  self.skipWaiting();
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))));
  self.clients.claim();
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(fetch(e.request).catch(() => new Response(
      JSON.stringify({ code: "OFFLINE", message: "当前离线，请求已交由客户端队列处理", data: null }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    )));
    return;
  }
  e.respondWith(
    fetch(e.request)
      .then(response => {
        const cloned = response.clone();
        caches.open(CACHE).then(c => c.put(e.request, cloned));
        return response;
      })
      .catch(() => caches.match(e.request))
  );
});
