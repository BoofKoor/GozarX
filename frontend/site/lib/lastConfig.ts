// The last config this browser was shown, kept in localStorage so /offline can hand it back when
// the network is gone (C-35/C-67) — the offline page promised «آخرین کانفیگ ذخیره‌شده‌ات این‌جاست»
// and had nothing to show. Written by the claim widget whenever the server confirms a live config,
// dropped when it confirms there is none (ended, reset, blocked), never touched while offline.
//
// The offline page reads this key from an INLINE script, not from React: offline, its JS chunks may
// not be in any cache, and a client component that never loads shows nothing. So the shape is
// plain JSON, and a change to it must be made in app/offline/page.tsx as well.

export const LAST_CONFIG_KEY = "gz_last_config";

export interface LastConfig {
  link: string;
  /** the remark (matching key) and what the reader was shown for it, in their language */
  location: string | null;
  label: string | null;
  /** UTC ISO instant the config runs out, when the server said */
  expires_at: string | null;
  saved_at: string;
}

export function saveLastConfig(config: Omit<LastConfig, "saved_at"> | null): void {
  try {
    if (!config) {
      localStorage.removeItem(LAST_CONFIG_KEY);
      return;
    }
    const prev = localStorage.getItem(LAST_CONFIG_KEY);
    const next: LastConfig = { ...config, saved_at: new Date().toISOString() };
    // skip a write that changes nothing but the timestamp — this runs on every status poll
    if (prev) {
      const old = JSON.parse(prev) as LastConfig;
      if (
        old.link === next.link &&
        old.label === next.label &&
        old.expires_at === next.expires_at
      ) {
        return;
      }
    }
    localStorage.setItem(LAST_CONFIG_KEY, JSON.stringify(next));
  } catch {
    // storage blocked (private mode, a strict browser): the offline page just has nothing to show
  }
}

export function readLastConfig(): LastConfig | null {
  try {
    const raw = localStorage.getItem(LAST_CONFIG_KEY);
    if (!raw) return null;
    const c = JSON.parse(raw) as LastConfig;
    // the same guard the offline page's inline script applies: a link must look like a URL
    return c && typeof c.link === "string" && /^[a-z][a-z0-9+.-]*:\/\//i.test(c.link) ? c : null;
  } catch {
    return null;
  }
}
