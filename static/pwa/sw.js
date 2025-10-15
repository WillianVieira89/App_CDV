// sw.js - cache estático + fallback leve
const CACHE = "cdv-l5-v1";
const PRECACHE = [
  "/",                          // homepage
  "/static/js/script.js",
  "/static/js/circuitos_por_estacao.js",
  "/static/pwa/manifest.json",
  // inclua CSS e imagens principais se tiver
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Estratégia: network-first para páginas dinâmicas; cache-first para estáticos
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // não cacheia POST/PUT/DELETE
  if (e.request.method !== "GET") return;

  // estáticos -> cache-first
  if (url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(e.request).then(resp => resp || fetch(e.request))
    );
    return;
  }

  // páginas -> network-first com fallback cache
  e.respondWith(
    fetch(e.request)
      .then(resp => {
        const clone = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return resp;
      })
      .catch(() => caches.match(e.request))
  );
});
