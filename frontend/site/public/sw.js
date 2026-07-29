/* GozarX service worker — Web Push handling + a minimal offline shell.
   Push payloads are JSON { title, body, url } sent by the backend (services/push.py). */

// Bump this whenever the offline shell changes — `activate` deletes every cache whose key isn't the
// current one, so a bump cleans out an older build's cached HTML (which references now-dead asset
// hashes) in one shot.
const CACHE = "gozarx-shell-v2";
const SHELL = ["/", "/status", "/offline"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
  );
  self.clients.claim();
});

// Network-first for navigations, falling back to the cached shell / offline page. API calls are
// never cached (device-scoped, must be live).
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" || new URL(req.url).pathname.startsWith("/api/")) return;
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          // Cache ONLY a real, successful same-origin page. Without the guard a deploy-time 502 (or
          // any error page) got cached and then served offline instead of /offline.
          if (res.ok && res.type === "basic") {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
          }
          return res;
        })
        .catch(() => caches.match(req).then((m) => m || caches.match("/offline"))),
    );
  }
});

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (_) {
    data = {};
  }
  const title = data.title || "GozarX";
  const options = {
    body: data.body || "",
    icon: "/icons/icon-192.png",
    badge: "/icons/icon-192.png",
    data: { url: data.url || "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      // Focus an existing tab AND steer it to the notification's target (e.g. /status); the old code
      // returned focus() without ever navigating, so the click landed on whatever tab was open.
      for (const client of list) {
        if ("focus" in client) {
          return "navigate" in client ? client.navigate(url).then((c) => (c || client).focus()) : client.focus();
        }
      }
      return self.clients.openWindow(url);
    }),
  );
});
