/* GozarX service worker — Web Push handling + a minimal offline shell.
   Push payloads are JSON { title, body, url } sent by the backend (services/push.py). */

// Bump this whenever the offline shell changes — `activate` deletes every cache whose key isn't the
// current one, so a bump cleans out an older build's cached HTML (which references now-dead asset
// hashes) in one shot.
// v3: /offline now hands back the last saved config (an inline script over localStorage), so an
// install still holding the v2 copy of it would keep the page that promised a config and showed none.
// v4: the shell's stylesheet, scripts and font are cached with it (C-67). Only the HTML was, so an
// offline load drew the saved config in the browser's default styles — or, where the cached page
// referenced a chunk nothing had kept, not at all.
const CACHE = "gozarx-shell-v4";
const SHELL = ["/", "/status", "/offline"];
// What a page needs to draw itself, as it names it: the build's hashed CSS/JS and the font.
const ASSET_RE = /(?:href|src)="(\/(?:_next\/static\/[^"]+\.(?:css|js)|fonts\/[^"]+\.woff2))"/g;
// Cached files beyond the shell pages are capped, oldest first: the build's hashes change on every
// deploy while this file (and so the cache's name) does not, so without a cap each deploy's chunks
// would pile up behind the last.
const MAX_ASSETS = 80;

async function precache() {
  const c = await caches.open(CACHE);
  const urls = new Set();
  for (const page of SHELL) {
    try {
      const res = await fetch(page, { credentials: "same-origin" });
      if (!res.ok) continue;
      await c.put(page, res.clone());
      const html = await res.text();
      for (const m of html.matchAll(ASSET_RE)) urls.add(m[1].replace(/&amp;/g, "&"));
    } catch (_) {
      /* offline at install time — the shell fills in on later visits */
    }
  }
  await Promise.all([...urls].map((u) => c.add(u).catch(() => {})));
}

async function trim(c) {
  const keys = await c.keys();
  const assets = keys.filter((k) => !SHELL.includes(new URL(k.url).pathname));
  for (const k of assets.slice(0, Math.max(0, assets.length - MAX_ASSETS))) await c.delete(k);
}

self.addEventListener("install", (event) => {
  event.waitUntil(precache().catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
  );
  self.clients.claim();
});

// Network-first for navigations, falling back to the cached shell / offline page. The build's
// assets are content-hashed, so a cached copy is always the right one: served from the cache first,
// and kept on the way through, so whatever a page loaded online is there for it offline. The font
// is not hashed — served from the cache too, but refreshed behind it. API calls are never cached
// (device-scoped, must be live).
self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
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
    return;
  }
  const hashed = url.pathname.startsWith("/_next/static/");
  if (!hashed && !url.pathname.startsWith("/fonts/")) return;
  event.respondWith(
    caches.open(CACHE).then(async (c) => {
      const hit = await c.match(req);
      const fresh = fetch(req)
        .then((res) => {
          if (res.ok && res.type === "basic") c.put(req, res.clone()).then(() => trim(c)).catch(() => {});
          return res;
        })
        .catch(() => hit || Response.error());
      if (hit) {
        if (!hashed) event.waitUntil(fresh);
        return hit;
      }
      return fresh;
    }),
  );
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
