// COFIRE offline support. Pages and forecast data are kept as they are fetched,
// so the newest forecast and brief stay readable without a connection. The
// staleness badge on the map and brief says how old they are.
const VERSION = "cofire-v1";
const SHELL = ["./"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(VERSION).then((c) => c.addAll(SHELL.map((p) => new URL(p, self.registration.scope).toString())).catch(() => undefined)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()),
  );
});

function isData(url) {
  return /\/domains(\/|$)|\/data\/|\/ember\/(checklist|score)|\/predictions\/me|\/leaderboard|\/observations/.test(url.pathname);
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.protocol !== "http:" && url.protocol !== "https:") return;

  // Hashed build files never change: cache first.
  if (url.pathname.includes("/_next/static/") || url.pathname.includes("/maplibre/")) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok) caches.open(VERSION).then((c) => c.put(req, res.clone()));
        return res;
      })),
    );
    return;
  }

  // Pages and forecast data: the network when it answers, the saved copy when not.
  if (req.mode === "navigate" || isData(url)) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(VERSION).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() =>
          caches.match(req, { ignoreSearch: req.mode === "navigate" }).then(
            (hit) => hit || (req.mode === "navigate" ? caches.match(new URL("./", self.registration.scope).toString()) : undefined) || Response.error(),
          ),
        ),
    );
  }
});
