// Service Worker: schnellerer Start + freundliche Offline-Meldung. Fotos/Daten (/api) werden NIE zwischengespeichert.
const VERSION = "v1";
const SCHALE = ["/", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(VERSION).then(c => c.addAll(SCHALE)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/")) return;
  // Oberflaeche: erst Netz (damit Updates sofort ankommen), sonst Zwischenspeicher
  e.respondWith(fetch(e.request).then(r => { if (r.ok) { const k = r.clone(); caches.open(VERSION).then(c => c.put(e.request, k)); } return r; })
    .catch(() => caches.match(e.request).then(r => r || caches.match("/"))));
});
