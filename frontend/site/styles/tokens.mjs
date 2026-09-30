// The site's colour tokens — the ONE place a theme colour is defined (C-58). The stylesheet needs
// each of them in four blocks (auto-light, auto-dark, [data-theme=light], [data-theme=dark]), and a
// token missing from one was a silent bug in that theme only: --skel-1/--skel-2 existed in none of
// the site's blocks, so every skeleton painted nothing. `npm run tokens` writes those four blocks
// into styles/tokens.css; `npm run build` refuses to build from a stale one.
//
// Seeded from docs/website/design/TOKENS.css (the design's consolidated tokens, AA-audited in both
// themes) and extended here: --grad-a/--grad-b (the headline gradient's measured pair) are the
// site's own. Keep the two themes' keys identical — the generator refuses a key only one of them has.
export const light = {
  "bg": "#F6F8FC", "surface": "#FFFFFF", "raised": "#FFFFFF", "sunken": "#F1F5F9", "sunken-2": "#EEF2F8",
  "border": "#E4E9F2", "border-strong": "#D3DAE6", "text": "#0F172A", "muted": "#5E6B80", "faint": "#7C8AA0",
  "primary": "#2563EB", "primary-2": "#1D4ED8", "primary-hover": "#1D4ED8", "on-primary": "#FFFFFF", "link": "#2563EB", "ring": "#3B82F6",
  "success": "#10B981", "success-surface": "#DCFCE7", "success-ink": "#047857",
  "warning": "#F59E0B", "warning-surface": "#FEF3C7", "warning-ink": "#B45309",
  "danger": "#EF4444", "danger-surface": "#FEE2E2", "danger-ink": "#B91C1C",
  "brand-tint": "#EFF5FF", "brand-tint-2": "#E0EBFF", "brand-tint-ink": "#1D4ED8",
  "glow": "0 8px 24px rgba(37,99,235,.32)", "glow-sm": "0 4px 14px rgba(37,99,235,.28)",
  "backdrop": "rgba(15,23,42,.5)", "logo-ink": "#0F172A", "logo-accent": "#2563EB",
  "hero-1": "#2563EB", "hero-2": "#06B6D4", "card-sheen": "rgba(6,182,212,.10)", "flag-ring": "rgba(2,6,23,.08)",
  "band": "#0B1220", "band-ink": "#E5EDFF", "accent": "#06B6D4", "skel-1": "#EAEFF7", "skel-2": "#F4F7FC",
  "grad-a": "#2563EB", "grad-b": "#0E7490",
};

export const dark = {
  "bg": "#020617", "surface": "#0E1729", "raised": "#182338", "sunken": "#0A1120", "sunken-2": "#111C31",
  "border": "rgba(148,163,184,.16)", "border-strong": "rgba(148,163,184,.28)", "text": "#F1F5F9", "muted": "#94A3B8", "faint": "#64748B",
  "primary": "#3B82F6", "primary-2": "#2563EB", "primary-hover": "#60A5FA", "on-primary": "#06132B", "link": "#60A5FA", "ring": "#3B82F6",
  "success": "#34D399", "success-surface": "rgba(16,185,129,.16)", "success-ink": "#6EE7B7",
  "warning": "#FBBF24", "warning-surface": "rgba(245,158,11,.16)", "warning-ink": "#FCD34D",
  "danger": "#F87171", "danger-surface": "rgba(239,68,68,.16)", "danger-ink": "#FCA5A5",
  "brand-tint": "rgba(59,130,246,.14)", "brand-tint-2": "rgba(59,130,246,.22)", "brand-tint-ink": "#93C5FD",
  "glow": "0 8px 28px rgba(59,130,246,.42)", "glow-sm": "0 4px 16px rgba(59,130,246,.36)",
  "backdrop": "rgba(2,6,23,.72)", "logo-ink": "#F1F5F9", "logo-accent": "#3B82F6",
  "hero-1": "#1E40AF", "hero-2": "#0E7490", "card-sheen": "rgba(6,182,212,.12)", "flag-ring": "rgba(255,255,255,.12)",
  "band": "#0A1120", "band-ink": "#E5EDFF", "accent": "#22D3EE", "skel-1": "#141F33", "skel-2": "#1C293F",
  "grad-a": "#60A5FA", "grad-b": "#22D3EE",
};
