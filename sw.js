/* MIRA Mind service worker — offline shell, cache-first, network fallback. */
var CACHE = "miramind-v1";
var ASSETS = [
  "./index.html",
  "./app.js",
  "./style.css",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-512.png",
  "./icons/apple-touch-icon.png"
];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return c.addAll(ASSETS).then(function () { return self.skipWaiting(); });
  }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.map(function (k) {
      return k !== CACHE ? caches.delete(k) : Promise.resolve();
    })).then(function () { return self.clients.claim(); });
  }));
});

/* Navigation must always load the freshest shell (network-first), so an
   update reaches users once they are online; assets use cache-first. */
self.addEventListener("fetch", function (e) {
  if (e.request.method !== "GET") return;
  var isNav = e.request.mode === "navigate" ||
    (e.request.headers.get("accept") || "").indexOf("text/html") !== -1;
  if (isNav) {
    e.respondWith(
      fetch(e.request).then(function (res) {
        return caches.open(CACHE).then(function (c) { c.put("./index.html", res.clone()); return res; });
      }).catch(function () { return caches.match("./index.html"); })
    );
    return;
  }
  e.respondWith(
    caches.match(e.request).then(function (hit) {
      if (hit) return hit;
      return fetch(e.request).then(function (res) {
        caches.open(CACHE).then(function (c) { c.put(e.request, res.clone()); });
        return res;
      });
    })
  );
});
