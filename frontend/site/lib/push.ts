"use client";

import { api } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const arr = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

// Request permission → subscribe via the service worker's PushManager (VAPID public key) → POST the
// subscription to the backend. Returns true only if a subscription was actually stored. Fully
// best-effort: unsupported browser / denied permission / missing key all resolve to false.
export async function subscribeToPush(vapidPublicKey: string, locale: Locale): Promise<boolean> {
  try {
    if (
      typeof navigator === "undefined" ||
      !("serviceWorker" in navigator) ||
      !("PushManager" in window) ||
      !vapidPublicKey
    ) {
      return false;
    }
    const perm = await Notification.requestPermission();
    if (perm !== "granted") return false;
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
    });
    const json = sub.toJSON();
    const res = await api.subscribePush({
      endpoint: sub.endpoint,
      p256dh: json.keys?.p256dh ?? "",
      auth: json.keys?.auth ?? "",
      locale,
    });
    return !!res.ok;
  } catch {
    return false;
  }
}
