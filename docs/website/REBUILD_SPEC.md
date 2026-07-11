# GozarX Website — Faithful Rebuild Blueprint (single source of truth)

Extracted verbatim from the approved design deliverables in `docs/website/design/`
(`phase-0` … `phase-7`, `TOKENS.css`, `UI_SPEC.md`, `assets/`). This document describes
exactly what to reproduce, pixel- and behavior-accurate, in the Next.js app under
`frontend/site/`. **Numbers shown are sample/demo values** — in the real build every
economic number (volume, hours, reward MB, invite cap) comes from `site_*` panel settings and
copy comes from the `content` table. The demos hardcode them only to render.

Every design file is a **self-contained HTML** with a `#app` root carrying
`data-theme` (`light`/`dark`), `data-locale` (`fa`/`en`), `dir` (`rtl`/`ltr`), `lang`. All
copy is injected from a JS `I = {fa:{…}, en:{…}}` dictionary; all layout uses **CSS logical
properties only** (no physical left/right). Fonts are embedded woff2 (fa = Yekan Bakh VF, en =
Inter Variable). Flags are real circular SVGs derived from the config remark emoji — never
rendered as emoji glyphs.

---

## 0. Global system

### 0.1 Design tokens (authoritative — from `TOKENS.css`, identical across all phase files)

Scope everything under `#app`. Primary brand: Gozar Blue `#2563EB` (light) / `#3B82F6` (dark).

**Radii / shadows / root box:**
```
--r-ctl:12px; --r-btn:14px; --r-card:16px; --r-lg:20px; --r-hero:26px; --r-pill:9999px;
--shadow-sm:0 1px 2px rgba(2,6,23,.06), 0 4px 12px rgba(2,6,23,.06);
--shadow-md:0 2px 6px rgba(2,6,23,.06), 0 12px 32px rgba(2,6,23,.10);
--shadow-hero:0 4px 14px rgba(2,6,23,.06), 0 28px 70px rgba(2,6,23,.20);
```
Root: `min-height:100vh; background:var(--bg); color:var(--text); font-family:var(--font);
line-height:var(--lh-body); font-size:16px; -webkit-font-smoothing:antialiased;
transition:background .25s,color .25s;`
Required reset: `#app *,*::before,*::after{box-sizing:border-box}` and
**`#app button{font-family:inherit}`** (critical — buttons don't inherit font, Persian text
would fall back to Arial otherwise).

**Light theme** (`#app[data-theme="light"]`):
```
--bg:#F6F8FC; --surface:#FFFFFF; --raised:#FFFFFF; --sunken:#F1F5F9; --sunken-2:#EEF2F8;
--border:#E4E9F2; --border-strong:#D3DAE6;
--text:#0F172A; --muted:#5E6B80; --faint:#7C8AA0;
--primary:#2563EB; --primary-2:#1D4ED8; --primary-hover:#1D4ED8; --on-primary:#FFFFFF;
--link:#2563EB; --ring:#3B82F6;
--success:#10B981; --success-surface:#DCFCE7; --success-ink:#047857;
--warning:#F59E0B; --warning-surface:#FEF3C7; --warning-ink:#B45309;
--danger:#EF4444; --danger-surface:#FEE2E2; --danger-ink:#B91C1C;
--brand-tint:#EFF5FF; --brand-tint-2:#E0EBFF; --brand-tint-ink:#1D4ED8;
--glow:0 8px 24px rgba(37,99,235,.32); --glow-sm:0 4px 14px rgba(37,99,235,.28);
--backdrop:rgba(15,23,42,.5); --logo-ink:#0F172A; --logo-accent:#2563EB;
--hero-1:#2563EB; --hero-2:#06B6D4; --accent:#06B6D4; --card-sheen:rgba(6,182,212,.10);
--flag-ring:rgba(2,6,23,.08); --band:#0B1220; --band-ink:#E5EDFF;
--skel-1:#EAEFF7; --skel-2:#F4F7FC;
/* rewards gauge only: */ --seg-base:#2563EB; --seg-inv:#8B5CF6; --seg-mis:#F59E0B;
```

**Dark theme** (`#app[data-theme="dark"]`):
```
--bg:#020617; --surface:#0E1729; --raised:#182338; --sunken:#0A1120; --sunken-2:#111C31;
--border:rgba(148,163,184,.16); --border-strong:rgba(148,163,184,.28);
--text:#F1F5F9; --muted:#94A3B8; --faint:#64748B;
--primary:#3B82F6; --primary-2:#2563EB; --primary-hover:#60A5FA; --on-primary:#06132B;
--link:#60A5FA; --ring:#3B82F6;
--success:#34D399; --success-surface:rgba(16,185,129,.16); --success-ink:#6EE7B7;
--warning:#FBBF24; --warning-surface:rgba(245,158,11,.16); --warning-ink:#FCD34D;
--danger:#F87171; --danger-surface:rgba(239,68,68,.16); --danger-ink:#FCA5A5;
--brand-tint:rgba(59,130,246,.14); --brand-tint-2:rgba(59,130,246,.22); --brand-tint-ink:#93C5FD;
--glow:0 8px 28px rgba(59,130,246,.42); --glow-sm:0 4px 16px rgba(59,130,246,.36);
--backdrop:rgba(2,6,23,.72); --logo-ink:#F1F5F9; --logo-accent:#3B82F6;
--hero-1:#1E40AF; --hero-2:#0E7490; --accent:#22D3EE; --card-sheen:rgba(6,182,212,.12);
--flag-ring:rgba(255,255,255,.12); --band:#0A1120; --band-ink:#E5EDFF;
--skel-1:#141F33; --skel-2:#1C293F; --seg-base:#60A5FA; --seg-inv:#A78BFA; --seg-mis:#FBBF24;
```

**Theme resolution logic (reproduce exactly):** on load read `<html data-theme>`; else fall to
`prefers-color-scheme: dark`. A `MutationObserver` on `<html data-theme>` mirrors host theme
changes into `#app`. Manual toggle wins.

### 0.2 Locale / fonts / digits

```
#app[data-locale="fa"]{ --font:"Yekan Bakh VF","Vazirmatn",Tahoma,"Segoe UI",system-ui,sans-serif;
                        --lh-body:1.8; --lh-head:1.55; --ls-head:0; }
#app[data-locale="en"]{ --font:"Inter Variable","Inter",system-ui,-apple-system,"Segoe UI",sans-serif;
                        --lh-body:1.6; --lh-head:1.2; --ls-head:-.01em; }
```
- Persian single-line chrome (`.btn .seg button .navlink .chip .badge .pill`) gets
  `line-height:1.4` so descenders never clip. Persian location labels `.loc-card .nm`:
  `font-size:13px; font-weight:500; line-height:1.75`.
- **Never letter-space Persian.** `--ls-head:-.01em` is EN only.
- Fonts self-hosted woff2, `font-display:swap`, weight range `100 950` (fa) / `100 900` (en).
  Files: `public/fonts/YekanBakh-VF.woff2`, `public/fonts/Inter-Variable-latin.woff2`.
- **Digit localization** — the `faD()` helper: in fa, replace each ASCII digit with
  `۰۱۲۳۴۵۶۷۸۹`; in en, pass through. Decimals in fa use `٫` (e.g. `۱٫۵`), thousands use `٬`
  (e.g. `+۱۲٬۰۰۰`). **Technical strings stay Latin & LTR** (config links, transfer codes,
  usernames) — never run them through `faD`.
- Unit helpers: `units_gb = "{n} گیگابایت" / "{n} GB"`, `units_mb = "{n} مگابایت" / "{n} MB"`.
  `volTxt(mb)` = GB if `mb>=1024` else MB. MB values use `toLocaleString("en-US")` then `faD`.
- Tabular numerals (`font-variant-numeric:tabular-nums`) on all counters/timers/meters/stats.

### 0.3 Container & rhythm
- `.container{ max-width: <PAGE>; margin-inline:auto; padding-inline:20px }`;
  `@min-width:768px → 32px`; `@max-width:359px → 16px`.
  Max-widths per page: homepage **1180px**; claim-widget page 1160px; rewards/landing/content
  **1120px**; status/pwa **1080px** (via `.container` in those files).
- Section vertical padding: homepage `.sec` 56px → `@768px` 80px; other pages 36–44px → 56px.
- 4px base grid throughout; deliberate 2px half-steps inside chips/meters/stat-rows.
- Type scale (px, desktop/mobile): display 56/36 · h1 40/30 · h2 32/26 · h3 24/20 · h4 20/18 ·
  body-lg 18/17 · body 16 · small 14 · caption 12.

### 0.4 Logo
Inline SVG symbol `#gz-logo`, viewBox `0 0 639 508`, two paths: main uses
`fill:var(--logo-ink)`, the trailing "X" stroke uses `fill:var(--logo-accent)` (blue). Header
logo `block-size:28px` (claim-widget toolbar 26px). Source at `assets/logo-mark.svg` /
`public/logo-mark.svg`. Wordmark "GozarX" beside it, `font-weight:800; font-size:17px`.

### 0.5 Icon set (inline 24×24 SVG, `fill:none; stroke:currentColor; stroke-linecap/linejoin:round`)
`svg(name, strokeWidth, className)` wraps each. Directional icons get class `ic-dir` and flip in
RTL via `[dir="rtl"] .ic-dir{transform:scaleX(-1)}`. Path data (reuse verbatim):
```
bolt   : M13 2 4.5 13.5H11l-1 8.5 8.5-11.5H12l1-8.5Z
check  : m5 13 4 4L19 7
shield : M12 2 4 5.5V12c0 5 3.5 8.5 8 10 4.5-1.5 8-5 8-10V5.5Z  +  m9 12 2 2 4-4
clock  : <circle 12,12 r9> + M12 7v5l3 2
gift   : <rect 3,8 18x4 rx1> + M12 8v13M5 12v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-8M12 8S10.5 3 8 4s0 4 4 4c4 0 6.5-3 4-4s-4 4-4 4Z
qr     : <rect 3,3 7x7 rx1><rect 14,3 7x7 rx1><rect 3,14 7x7 rx1> + M14 14h3v3h-3zM19 19h2v2h-2z
gauge  : M12 13a3 3 0 0 0 3-3M4 15a8 8 0 1 1 16 0
globe  : <circle 12,12 r9> + M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z
warn   : M12 3 2 20h20L12 3Z + M12 10v4M12 17v.5
plug   : M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0V8ZM12 17v5
spark  : M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18
share  : <circle 18,5 r3><circle 6,12 r3><circle 18,19 r3> + m8.6 13.5 6.8 4M15.4 6.5 8.6 10.5
help   : <circle 12,12 r9> + M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.8.4-1 .9-1 1.7M12 17v.5
arrow  : M5 12h14M13 6l6 6-6 6            (ic-dir)
swap   : M7 4 3 8l4 4M3 8h13M17 20l4-4-4-4M21 16H8
users  : <circle 9,8 r3.2> + M3.5 20a5.5 5.5 0 0 1 11 0M16 6a3.2 3.2 0 0 1 0 6M18.5 20a5.5 5.5 0 0 0-3-4.9
download: M12 3v12m0 0 4-4m-4 4-4-4M5 21h14
bell   : M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6M9.5 20a2.5 2.5 0 0 0 5 0
chev   : m6 9 6 6 6-6      chevR: m9 6 6 6-6 6 (ic-dir in breadcrumbs)
cal    : <rect 3,4 18x17 rx2> + M3 9h18M8 2v4M16 2v4
pin    : M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11Z + <circle 12,10 r2.5>
device : <rect 7,3 10x18 rx2> + M11 18h2
send   : M4 12h13M11 6l6 6-6 6   (homepage) / m22 2-11 11M22 2 15 22l-4-9-9-4Z (content, ic-dir)
trash  : M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13
search : <circle 11,11 r7> + m20 20-3.5-3.5
moon (theme): M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z
sun  (theme): <circle 12,12 r4.5> + M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19
burger : M4 7h16M4 12h16M4 17h16
close  : M6 6l12 12M18 6 6 18
star (popular, filled): M12 2.6l2.7 5.5 6 .9-4.35 4.24 1.03 6L12 16.9l-5.38 2.84 1.03-6L3.3 9l6-.9z
```
PWA/system extra icons: `belloff, wifioff, retry/refresh, wrench, ghost, news, info, play, book,
android, apple, windows, terminal, mail` (see phase-7/phase-5 for exact paths).

### 0.6 Icon flip table (RTL)
- **Flip** (`.ic-dir`, `scaleX(-1)`): arrow, chevron in breadcrumb `sep`, "next/back", send,
  CTA trailing arrow (also translateX hover flips sign), `.m-chip` hover translateX, mission
  `transform:translateX`, "get →" affordances.
- **Never flip** (symmetric): shield, globe, download, QR, check, bolt, gift, bell, gauge,
  clock, star, users, spark, close, burger.
- Gradients & radial decorations mirror angle in RTL: linear `135deg → 225deg`; radial
  `at 100% 0% → at 0% 0%`; hero/band `::before{ [dir=rtl]{transform:scaleX(-1)} }`.
- Progress bars/steppers/gauges run inline-start → inline-end; gauge SVG adds
  `[dir="rtl"]{transform:rotate(-90deg) scaleY(-1)}`.

### 0.7 Global chrome components (shared by every page except claim-widget preview toolbar)

**Header** `header.hd` — sticky, `inset-block-start:0; z-index:60;
background:color-mix(in srgb,var(--bg) 82%,transparent); backdrop-filter:blur(14px);
border-block-end:1px solid var(--border)`. Row `.hd-row{display:flex; gap:16px; padding-block:12px}`.
Contents in order: brand logo+wordmark → `nav.mainnav` (hidden `<1000px`, `display:flex ≥1000px`)
→ `.hd-spacer` → controls `.hd-ctrls`: language `.seg` (فا / EN pill segmented) · theme toggle
`.icon-only` (moon/sun swap by theme) · "My status" ghost/secondary button (`.status-btn`, shown
`≥1000px`) · burger `.icon-only` (shown `<1000px`).
- `.navlink`: `font-size:14.5px; font-weight:600; color:var(--muted); padding:8px 12px;
  border-radius:10px`. `.active{color:var(--link); background:var(--brand-tint)}`. hover
  `background:var(--sunken)`.
- `.seg` pill toggle: `padding:3px; gap:2px; background:var(--surface); border:1px solid var(--border);
  border-radius:pill`. buttons 13px/600 muted; `[aria-pressed=true]{background:var(--primary);
  color:var(--on-primary); font-weight:700}`.
- `.icon-only`: 38×38, `border-radius:11px`, bordered; hover border→primary. At `≤360px` → 36×36.

**Mobile bottom-sheet menu** — overlay `.sheet-ov{position:fixed; inset:0; z-index:80;
background:var(--backdrop)}` (`.open` shows). `.sheet{position:fixed; inset-inline:0;
inset-block-end:0; z-index:81; background:var(--surface); border-start-*-radius:var(--r-hero);
box-shadow:var(--shadow-hero); padding:12px 20px 24px; transform:translateY(100%);
transition:transform .3s ease; max-block-size:86vh; overflow-y:auto}` (`.open{transform:translateY(0)}`).
Top drag handle `.sheet-handle` 44×4 pill. Nav links stacked with leading icons; a separator
`.sheet-sep`; a full-width CTA "My status"; a locale segmented control. Opens on burger; closes on
overlay click or any `[data-close-sheet]` link.

**Language-suggestion banner** (homepage) `.lang-banner` — brand-tint strip above header, shown
only when `navigator.language` locale ≠ page locale. Centered text + underlined switch link +
`✕` dismiss. **Never auto-redirects.** fa: `"این سایت به انگلیسی هم موجود است."` + CTA
`"View in English"`; en: `"This page is also available in Persian."` + CTA `"نمایش به فارسی"`.

**Footer** `footer.ft` — `border-block-start`, `background:var(--surface)`. `.ft-grid`: 2-col
mobile → `1.6fr 1fr 1fr 1fr` `≥820px`. Column 1 = brand + tagline `.ft-tag`. Columns:
- Product: Get config · Locations · More volume · My status
- Resources: Setup guides · FAQ · Blog · About
- Legal: Terms of use · Privacy · Contact
`.ft-col h4` uppercase muted 13px. `.ft-bottom`: copyright (`© 1404 …` fa / `© 2025 …` en) +
language pill toggle. **No social/messenger links anywhere, sitewide.**

**Toasts** `#toasts{position:fixed; inset-block-start:74px; inset-inline-end:16px; z-index:90;
display:flex; flex-direction:column; gap:8px; max-inline-size:min(90vw,340px)}`. A toast is a
`.toast` card: raised bg, `border-inline-start:4px solid var(--success)`, check icon + text,
`animation:reveal/pop .25s`, auto-removed after ~2.4–3s. **Position rationale (documented in
phase-7):** top / inline-end via logical props → top-**left** in Persian, top-**right** in
English, below sticky header, opposite the logo so it never covers reading flow or nav.

**Buttons** `.btn` base: `display:inline-flex; gap:9px; border:1px solid transparent;
border-radius:var(--r-btn); font-size:15px; font-weight:700; padding:11–12px 18px;
background:var(--primary); color:var(--on-primary)`. `:active{transform:scale(.985)}`.
`:focus-visible{outline:2px solid var(--ring); outline-offset:2px}`. Variants: `.secondary`
(surface bg, strong border, hover→primary tint), `.ghost` (transparent, link/text color),
`.danger`, `.lg` (16px/14×24), `.sm`, `.block` (`inline-size:100%`), `.grad` (hero gradient).
**Primary claim CTA** `.cta`: full-width, 16.5px/800, `border-radius:16px`, white text,
`background:linear-gradient(135deg,var(--hero-1),color-mix(hero-1 55% hero-2))` (RTL → 225deg),
`box-shadow:var(--glow)`; hover brightens + 4px ring; a diagonal **sheen sweep** on hover
(`::after` gradient translateX -120%→120%, `@keyframes sheen 1.1s`); trailing arrow slides on
hover. Dark theme text `#EAF2FF`.

**Copy-field** `.copyfield` — `display:flex; gap:8px`. `code{direction:ltr;
unicode-bidi:isolate; text-align:left; font-family:ui-monospace,"SF Mono",Consolas,monospace;
white-space:nowrap; overflow-x:auto; scrollbar hidden; background:var(--sunken); border;
border-radius:var(--r-ctl); padding:~12px}` + copy button. On copy: `navigator.clipboard.writeText`,
button text → localized "Copied", class `.copied{background:var(--success); color:#fff}` (dark
`#04231a`), reverts after ~1.4s. **This is the mandatory pattern for every config link / invite
link / transfer code — always an LTR monospace island even inside RTL.**

**Skeleton** `.reveal{opacity:0; transform:translateY(16px); transition .5s}.reveal.in{...}` used
for scroll-triggered fade-up via IntersectionObserver (threshold ~.08–.12). All motion respects
`@media (prefers-reduced-motion:reduce)` → durations `.01ms`, reveals show immediately.

---

## 1. THE CLAIM WIDGET (Phase 1 — the heart of the product)

The widget is a large elevated card that is the homepage hero and is embedded on landing pages.
`.widget{position:relative; background:var(--surface); border; border-radius:var(--r-hero);
box-shadow:var(--shadow-hero); padding:20px (≥400px 24px); isolation:isolate}` with a corner
sheen `::before{radial-gradient(120% 78% at 100% 0%, var(--card-sheen), transparent 58%)}`
(RTL → `at 0% 0%`). Desktop hero grid: copy column + widget column
`minmax(392px,428px)` at `≥940px`.

### 1.1 Dynamic model (demo values — replace with `site_*` settings)
`CFG = { dailyGB:1, trialHours:24, rewardMB:500, invitesDone:3, invitesCap:10, usedMB:380,
totalMB:1024 }`. Sample link:
`vless://a1b2c3d4-e5f6-7890-ab12-cd34ef567890@de1.gozarx.net:443?type=ws&security=tls&sni=gozarx.net#GozarX-Germany`.
Invite link: `https://gozarx.net/i/GZR-4821`. Missions strip rewards: invite `+500 MB`,
PWA `+200 MB`, push `+150 MB`.

### 1.2 Locations (order fixed in demo; runtime from trial squad in prod)
`LOCS` array, each `{flag emoji, fa, en, rec?}`:
| # | emoji | fa | en | flag file | popular |
|---|-------|----|----|-----------|---------|
| 1 | 🇩🇪 | آلمان | Germany | `de.svg` | ★ rec |
| 2 | 🇺🇦 | اوکراین | Ukraine | `ua.svg` | |
| 3 | 🇺🇸 | آمریکا | USA | `us.svg` | |
| 4 | 🇹🇷 | ترکیه | Turkey | `tr.svg` | |
| 5 | 🇫🇷 | فرانسه | France | `fr.svg` | |
| 6 | 🇬🇧 | انگلیس | UK | `gb.svg` | |
| 7 | 🇳🇱 | هلند | Netherlands | `nl.svg` | |
| 8 | 🇨🇦 | کانادا | Canada | `ca.svg` | |

**Flag rendering (reproduce exactly):** `emojiToCC(emoji)` maps regional-indicator codepoints
`0x1F1E6–0x1F1FF` → subtract `0x1F1E6`, add `97` → 2-char ISO alpha-2. Then render
`<img class="flag" src="/flags/{cc}.svg">`. Flags are circular
(`border-radius:50%; box-shadow:0 0 0 1px var(--flag-ring); object-fit:cover`). Sizes: grid card
40px, config-line 34px, big location cards 52px, chips 20px, history 30px. The 8 SVGs already
live in `frontend/site/public/flags/` (circular masked, viewBox 512). **Match location→config by
remark NAME, never list index.**

### 1.3 Widget sub-parts

- **Header** `.w-head`: 42×42 gradient badge (bolt icon) + title/subtitle `.wt` + allowance pill
  `.allowance` (`margin-inline-start:auto`, brand-tint, bolt icon, e.g. «۱ گیگابایت امروز»).
  Compact variant omits subtitle. On homepage `≤460px` the header stacks vertically.
- **Location picker** `.pick-label` (label + count e.g. «۸ لوکیشن») then `.loc-grid`
  `repeat(3,1fr)` (`≥520px repeat(4,1fr)`, gap 8→10). Each `.loc-card` is a
  `<button role="radio" aria-pressed>`: circular flag with green online dot `.loc-online`
  (top inline-end), name, single-select. Selected: primary border + brand-tint bg + 3px ring +
  a check badge `.loc-check` (top inline-end). "Popular" tab `.loc-rec` (star + label) floats on
  the top edge inline-start, hidden when selected. Radiogroup semantics.
- **CTA block** `.cta-wrap`: `.cta` button (bolt + label + arrow), then reassurance row
  `.reassure` (three check items: no signup · free · renews every {h}h), then anti-bot note
  `.antibot` (shield icon, faint) «با یک بررسی نامرئی در برابر ربات محافظت می‌شود».
- **App quick-actions** `.apps`: label (platform-aware) + row of `.app-btn` (app icon + name).
- **QR toggle** `.cfg-actions` button `.icon-btn` (qr icon + "QR code") toggles `.qr-panel.show`
  → white `.qr-box` with a 33×33 canvas drawn pixelated (deterministic PRNG demo QR; finder
  squares use brand blue center). Redraw on theme change.
- **Usage meter** `.meter`: row (gauge icon + "Today's usage" · "380 MB of 1 GB") + `.bar` track
  with `>i` fill `linear-gradient(90deg,var(--primary),color-mix(primary 60% hero-2))`;
  `.bar.warn` (amber) at `≥80%`, `.bar.full` (danger) at 100%.
- **Segmented countdown** `.cd` (`direction:ltr; unicode-bidi:isolate`): three `.seg` tiles
  (HH / MM / SS, 24px/800 tabular) separated by colons, with a label above. Ticks every 1s via
  `setInterval`, `data-remain` seconds, `hms` padding, digits localized (fa Persian digits).
- **Missions strip** `.missions` (dismissible, `.hide`): header (gift icon + "Want more daily
  volume?" + `×` close) + `.m-chips` column of `.m-chip` rows (icon tile + title/desc + reward
  pill `.rw` e.g. `+۵۰۰ مگابایت`). Rows: Invite friends (users) · Install web app (download) ·
  Enable notifications (bell). No login/account upsell.
- **Config location line** `.cfg-loc`: flag 34 + name + "Ready" success pill.
- **Status header** `.status-head`: 46×46 rounded status icon (`.ok` success-surface,
  `.wait` brand-tint, `.warn` warning-surface, `.empty` sunken, `.err` danger-surface) + title +
  description.
- **Revive block** `.revive` (warning-surface, warning border): spark icon + "Revive this exact
  config" title + rich body (bold fragments), invite copy-field + native **Share** button
  (Web Share API) + a hidden `.revived-note` success confirmation (`.show`) + a demo
  "Simulate a successful invite" ghost button.
- **Center states** `.center-state`: 66×66 art tile (globe for empty, plug for error) + title +
  desc + action button(s).

### 1.4 App buttons (Streisand / v2rayNG / Happ — NOT Hiddify)
`APPS = { v2rayng:{n:"v2rayNG", tile #4338CA→#1E1B4B "V2"}, streisand:{n:"Streisand",
#28B7E8→#0E7FC0 "S"}, happ:{n:"Happ", #7C5CFF→#5B3EE0 "H"} }`. Real icons at
`public/icons` (source `assets/apps/v2rayng.png` 192², `streisand.webp`, `happ.webp`); rendered
26×26 rounded-8 with inset ring; fallback = gradient tile + initial when no icon.
**Platform detection** `detectPlatform()` (UA): android → `/android/i`; iOS →
`/iphone|ipad|ipod/i` OR (`/macintosh/i` && `maxTouchPoints>1`); else desktop.
`PLATFORM_APPS = { ios:[streisand,happ], android:[v2rayng,happ], desktop:[happ,v2rayng,streisand] }`.
Apps-row label is platform-aware: ios "For your iPhone" / android "For your Android" / else
"Open in app". App-card platform labels (homepage): v2rayNG "Android", Streisand "iOS · macOS",
Happ "iOS · Android · Desktop".

### 1.5 The eight states + compact variant (EXHAUSTIVE — each is a full render)

Gallery maps each to a backend code. Reproduce all:

| # | State (gallery title fa / en) | Backend code | Contents |
|---|---|---|---|
| **S1** | حالت اولیه (اولین بازدید) / Idle (first visit) | `Idle` | header + location grid (no selection or preset) + CTA block. |
| **S2** | در حال آماده‌سازی / Provisioning | `provisioning` | header + grid **disabled** (opacity .55, pointer-events none, selection forced to index 0) + CTA morphs to spinner + "Preparing your config…". Feels <3s (demo `setTimeout 1600–1700ms`). |
| **S3** | دریافت موفق / Claimed successfully | `Provisioned` | `.cfg` reveal (fade-up). status-head `.ok` (check) + "Your config is ready 🎉" + subtitle. Then: config-loc line, link label + copy-field, apps row, QR toggle, usage meter **0 of 1 GB**, divider, countdown "Time left" (demo 86340s ≈ 23:59:00), **missions strip**. |
| **S4** | کانفیگ فعال (بازگشت کاربر) / Active config (returning) | `AlreadyActive` | status-head `.ok` + "Your config is active" + subtitle. config-loc, copy-field, apps, QR, usage meter **380 MB of 1 GB**, divider, countdown (demo 53400s ≈ 14:50:00), then a full-width **secondary "Change location"** button (swap icon) that re-opens the location chips inline — instant switch, no new claim. |
| **S5** | کول‌داون (امروز گرفته) / Cooldown (already claimed today) | `AlreadyClaimedToday` | status-head `.wait` (clock) + "You've claimed today's config" + subtitle. Live countdown "Next config in" (demo 25964s ≈ 07:12:44, derived from user's own last claim) + **missions strip** (so the wait converts). |
| **S6** | حجم تمام‌شده + زنده‌سازی / Data exhausted + revive | `LIMITED · revive` | status-head `.warn` (warn) + "Today's volume is used up" + "Your config still has time — only its data ran out." Usage meter **full** (`.bar.full`). Golden **revive** block: "Revive this exact config" — invite one friend, config revives instantly; invite-link copy-field + native **Share** button; hidden revived confirmation; "Simulate a successful invite" demo button that shows the confirmation. |
| **S7** | بدون لوکیشن / آماده‌نبودن / No locations · not ready | `NoLocations · NotReady` | `.center-state`: globe art (`.empty`), "Locations are being refreshed", "No location is ready to claim yet…", secondary button → **"See the FAQ"**. |
| **S8** | خطای موقت پنل / Transient panel error | `PanelError` | `.center-state`: plug art (`.err`), "Something hiccuped", "No worries — your claim is untouched. Give it one more try.", a **single Retry** button + a ghost "Help & support". Never blames the user; one retry only. |
| **Compact** | واریانت فشرده / Compact (SEO landings) | `landing embed` | Shorter header (title = "Free {loc} config", subtitle "Ukraine is pre-selected"), allowance chip, location grid with location **pre-selected**, CTA. Zero extra clicks between landing and claim. |

**Interactions:** pick-loc toggles aria-pressed within `.loc-grid` and updates hero selection;
claim → provisioning → success (setTimeout); change-loc / retry → back to idle; copy → clipboard +
"Copied" feedback; qr → toggle panel + draw; dismiss → hide missions; share → Web Share API (else
toast); revive-demo → show revived note + disable button.

### 1.6 Claim widget copy (quote verbatim)

| key | fa | en |
|---|---|---|
| hero_eyebrow | کانفیگ رایگان روزانه | Free daily config |
| hero_title | کانفیگ رایگان امروزت را در چند ثانیه بگیر | Get today's free config in seconds |
| hero_sub | یک لوکیشن انتخاب کن و دکمه را بزن — بدون ثبت‌نام، بدون پرداخت. هر ۲۴ ساعت یک کانفیگ تازه، و با دعوت دوستان حجم روزانه‌ات بیشتر می‌شود. | Pick a location and press the button — no signup, no payment. A fresh config every 24 hours, and your daily volume grows as you invite friends. |
| trust1/2/3 | بدون ثبت‌نام · همیشه رایگان · هر ۲۴ ساعت تازه | No signup · Free forever · Fresh every 24h |
| w_title / w_sub | کانفیگ رایگان امروز / یک لوکیشن انتخاب کن و بگیر | Today's free config / Pick a location and claim |
| allowance | {v} امروز | {v} today |
| pick / pick_count | لوکیشن را انتخاب کن / {n} لوکیشن | Choose a location / {n} locations |
| rec | محبوب | Popular |
| cta_get / cta_prep | دریافت کانفیگ / در حال آماده‌سازی کانفیگ… | Get config / Preparing your config… |
| reassure1/2/3 | بدون ثبت‌نام / رایگان / هر {h} ساعت تازه | No signup / Free / Renews every {h}h |
| antibot | با یک بررسی نامرئی در برابر ربات محافظت می‌شود | Protected against bots by an invisible check |
| succ_title / succ_sub | کانفیگ آماده است / لینک را کپی کن یا در اپ باز کن. | Your config is ready / Copy the link or open it in an app. |
| active_title / active_sub | کانفیگ شما فعال است / می‌توانی کپی کنی یا لوکیشن را عوض کنی. | Your config is active / Copy it, or switch its location. |
| ready / link_label / copy / copied | آماده / لینک کانفیگ / کپی / کپی شد | Ready / Config link / Copy / Copied |
| show_qr / open_in / open_ios / open_android | کد QR / باز کردن در اپ / برای آیفون شما / برای اندروید شما | QR code / Open in app / For your iPhone / For your Android |
| time_left / usage / of / change_loc | زمان باقی‌مانده / مصرف امروز / از / تغییر لوکیشن | Time left / Today's usage / of / Change location |
| cd_h/cd_m/cd_s | ساعت / دقیقه / ثانیه | hours / min / sec |
| m_title | حجم بیشتری می‌خواهی؟ | Want more daily volume? |
| m_invite / _d | دعوت دوستان / به‌ازای هر دعوت موفق | Invite friends / per successful invite |
| m_pwa / _d | نصب وب‌اپ / یک‌بار، همیشگی | Install web app / one-time, permanent |
| m_push / _d | روشن‌کردن اعلان‌ها / یک‌بار | Enable notifications / one-time |
| cd_title / cd_sub / cd_next | کانفیگ امروزت را گرفتی / به‌محض پایان شمارش، کانفیگ تازه بگیر. / کانفیگ بعدی تا | You've claimed today's config / When the timer ends, grab a fresh one. / Next config in |
| ex_title / ex_sub | حجم امروزت تمام شد / زمان کانفیگ باقی است، فقط حجمش تمام شده. | Today's volume is used up / Your config still has time — only its data ran out. |
| revive_t | همین کانفیگ را زنده کن | Revive this exact config |
| revive_d | فقط **یک دوست** را دعوت کن؛ به‌محض اینکه اولین کانفیگش را بگیرد، همین کانفیگ تو **همان لحظه** دوباره فعال می‌شود — بدون صبرکردن تا فردا. | Invite just **one friend**; the moment they claim their first config, yours comes back to life **instantly** — no waiting until tomorrow. |
| invite_label / share / revive_demo | لینک دعوت تو / اشتراک‌گذاری / شبیه‌سازی دعوت موفق | Your invite link / Share / Simulate a successful invite |
| revived | یک دوست دعوتت را پذیرفت — کانفیگ دوباره فعال شد! ✨ | A friend accepted your invite — your config is live again! ✨ |
| empty_title / empty_sub / empty_link | لوکیشن‌ها در حال به‌روزرسانی‌اند / هنوز لوکیشنی آماده نیست. چند دقیقهٔ دیگر دوباره سر بزن. / مشاهدهٔ سوالات متداول | Locations are being refreshed / No location is ready to claim yet. Check back in a few minutes. / See the FAQ |
| err_title / err_sub / err_retry / err_help | یک وقفهٔ کوتاه پیش آمد / نگران نباش، دریافت تو دست‌نخورده مانده. یک‌بار دیگر تلاش کن. / تلاش دوباره / راهنما و پشتیبانی | Something hiccuped / No worries — your claim is untouched. Give it one more try. / Try again / Help & support |
| cmp_title2 / cmp_sub | کانفیگ رایگان اوکراین / لوکیشن اوکراین از قبل انتخاب شده | Free Ukraine config / Ukraine is pre-selected |

---

## 2. HOMEPAGE (Phase 2) — container 1180px

Section order top→bottom (each `<section class="sec">`, alternating `background:var(--sunken)`):

1. **Language banner** (conditional, above header) → **Header** (sticky).
2. **HERO** `.hero` — soft brand radial gradient (RTL-mirrored). Grid: copy column + widget
   column `minmax(400px,432px)` at `≥940px`. Copy: eyebrow chip, gradient H1
   (`hero_h1_a` + `<span class="grad">hero_h1_b</span>` — the second fragment uses
   `background:linear-gradient(120deg,hero-1,hero-2)` clipped to text), supporting `.sub`, and a
   **trust-row** of 4 `.pill`s: No signup · Free forever · Fresh every 24h · **12,000+ users**
   (`+۱۲٬۰۰۰ کاربر`, users icon). The widget renders live in **S1 Idle**.
3. **HOW IT WORKS** `#how` — eyebrow "Three simple steps" + title "How it works" + sub. Three
   `.step` cards in `.steps` (`repeat(3)` `≥760px`) with number/icon tile, h3, p, and a
   direction-aware connector line `.conn` between cards. Steps: Pick a location (pin) → Get the
   config (bolt) → Import into your app (download).
4. **LOCATIONS** `#locations` (sunken bg) — eyebrow/title/sub + `.locrow` grid of 8 `.locbig`
   cards (`repeat(2)` → `repeat(4)` `≥640px`): 52px flag, name, "Get →" affordance. Below:
   centered "See all locations" link.
5. **MORE VOLUME** `#rewards` — 4 `.mcard` mission cards in `.missiongrid`
   (1→2→4 cols): Invite friends (users, +500 MB) · Install web app (download, +200 MB) · Enable
   notifications (bell, +150 MB) · Daily check-in (cal, "streak volume"). Each: icon tile, h3,
   desc, reward pill `.rw` (bolt + value). "See all missions" link.
6. **APPS** `#apps-sec` (sunken bg) — `.approw` of `.appcard`s (`repeat(3)` `≥760px`) ordered by
   detected platform: 52px app icon + name + platform label + trailing arrow. Links to guides.
7. **STATS band** — dark `.band` card (`background:var(--band)`, radial cyan/blue decoration,
   RTL-mirrored), 3 stats (`repeat(3)`, stack `≤560px` with divider): configs delivered
   (`۲٫۴M`/`2.4M`) · active locations (`۸`/`8`) · uptime (`۹۹٫۹٪`/`99.9%`). Tabular; count-up on
   reveal.
8. **FAQ teaser** `#faq` (sunken bg) — top-5 `.acc` accordions (first open). "See all questions".
9. **TRUST band** — centered `.trust-card` with shield tile, title "No signup. No tracking.",
   sub, three `.tb` badges (No email · No phone · No signup), "Read about privacy" link. Radial
   brand-tint decoration.
10. **BLOG teaser** `#blog` (sunken bg) — 3 `.post` cards (`repeat(3)` `≥720px`): gradient cover
    with tag badge, title, meta (read-time · GozarX).
11. **FOOTER**.
12. Fixed review-only `.devbar` (platform preview toggle) — **omit in production**.

Interactions: nav active-page indicator; accordions toggle `data-open`; scroll reveals;
count-up; language banner; mobile sheet. Homepage FAQ copy (5 Q/A) quoted in the file
(`faq1_q…faq5_a`) — e.g. faq1 "Is the free config really free?" / "کانفیگ رایگان واقعاً رایگان
است؟". Trust band: "بدون ثبت‌نام. بدون ردگیری." / "No signup. No tracking." Hero H1 fa =
«کانفیگ رایگان و پرسرعت، در چند ثانیه»; en = "Free, fast configs — in seconds".

---

## 3. REWARDS / "More volume" (Phase 3, `/rewards`) — container 1120px

Model: `CFG = { baseMB:1024, rewardMB:500, invitesDone:3, invitesCap:10, pwaMB:200, pushMB:150,
streakMB:300, streakDays:7, streakDone:3 }`.

Section order:
1. **Page head** — eyebrow (gift), H1 "Grow your daily volume" / «حجم روزانه‌ات را بیشتر کن»,
   sub (everything stored on this device).
2. **GAUGE hero** `.gauge-card` (`auto 1fr` `≥680px`): a 190px conic **ring gauge** (SVG,
   `r=82`, three colored arcs `--seg-base`/`--seg-inv`/`--seg-mis` with a 6px gap, rotate -90°,
   RTL flips `scaleY(-1)`), center shows big number + unit + "per day". Right side `.breakdown`:
   "Your current daily volume" + sub + `.legend` (Base volume / Friend invites / Missions with
   swatch + value). Arc math: fractions of total, `stroke-dasharray`/`dashoffset` animated .6s.
3. **INVITE card** `.invite` (primary-tinted border, corner sheen): header (users tile, "Invite
   friends", "The strongest way to grow your volume", reward tag `+500 MB per friend`), invite
   **copy-field** (LTR), a **grad Share button** (Web Share API → sheet, else toast), progress
   block "Successful invites" `۳ / ۱۰` with a **segmented bar** `.segbar` (10 segments, `.on`
   filled = gradient), and a warning-surface **revive note** ("If today's volume runs out, just
   **one successful invite** revives that same config **instantly**.").
4. **MISSIONS grid** `.mgrid` (1→2→3 cols) of `.mcard` with `data-state`:
   - **available**: icon tile, reward pill, h3, desc, **grad claim button** (bottom).
   - **done**: success border + tint, "Claimed" state-tag (check).
   - **prog** (in-progress, e.g. streak): "In progress" tag (clock). Streak card shows a
     `.streak` row of `streakDays` dots (`.on` filled gradient, `.today` outlined) + caption
     "{a} of {d} days — come back tomorrow!".
   - **unavailable**: opacity .72, "Not on this device" tag (ban) + a `?` tooltip `.why .tip`
     explainer (e.g. iOS web-notification limitation).
   Demo missions: Install web app (download, +200 MB) · Enable notifications (bell, +150 MB) ·
   Daily check-in (cal, +300 MB, streak/prog). Claim → card flips to done + toast
   "{v} added to your daily volume!"; gauge re-draws.
5. **State reference** section — 4 non-interactive `.mcard` demonstrating available / in-progress
   / claimed / unavailable, + **fine-print** block `.fineprint` (info icon + 4 rules: once per
   device · rewards add to daily volume · unfair use voids · amounts from panel settings).
6. Footer.

Key copy: p_title «حجم روزانه‌ات را بیشتر کن» / "Grow your daily volume"; bd_title «حجم روزانهٔ
فعلی شما» / "Your current daily volume"; inv_reward "{v} به‌ازای هر نفر" / "{v} per friend".

---

## 4. SEO LANDING TEMPLATE + LOCATIONS INDEX (Phase 4) — container 1120px

One reusable template driven by a `LANDINGS` config object; demoed with **Ukraine** (location,
`/location/ukraine`), **USA static IP** (keyword, `/l/usa-static-ip`), and the **locations index**
(`/locations`). Model `CFG={dailyGB:1, trialHours:24}`; `LOCS` carries `slug`.

**Landing template** structure (top→bottom):
1. **Breadcrumb** `.crumbs` — Home › Locations|Keywords › {H1}. Chevron separators flip in RTL.
2. **Landing hero** `.lhero` (`minmax(0,1fr) minmax(380px,410px)` `≥940px`): eyebrow chip
   (spark + `eyebrow`), H1 (exact keyword), one-line `.promise`, quick-trust chips (`.qt`:
   No signup · Free · Every {h}h), and the **compact claim widget with location pre-selected**
   (`widgetHTML(v)` — idle → provisioning → success flow identical to Phase 1, condensed).
3. **Benefit trio** `.btrio` (`repeat(3)` `≥700px`) — 3 `.bcard`s (icon tile + h3 + p) specific to
   the location (latency / use-cases / IP type).
4. **How to use it** `.steps` — 3 `.step`s (numbered), step 3 links to platform guides
   (Android/iPhone/Windows).
5. **SEO prose** `.prose` (`max-width:38rem`, line-height 1.9) — H2/H3 + paragraphs with inline
   LTR islands `.isl` for technical terms (`vless://…`, `v2rayNG`).
6. **Location FAQ** `.faqwrap` — 4 `.acc` accordions (first open) → carries FAQPage schema.
7. **Related** `.rel-group` — other-location chips (`.chip` with flag) + related keyword chips
   (Free v2ray config / Free daily VPN / Free VLESS config).
8. **CTA band** `.ctaband` (dark `--band`, radial decoration) — repeats H1 + promise + a
   scroll-to-top get button.

**Locations index** `/locations`: breadcrumb + H1 "All locations" + intro paragraph + a **search
input** `.idx-search` (client filter by localized+en name, empty state
"No country matches that name.") + `.idx-grid` (2→3→4 cols) of `.idx-card`s (52px flag, name,
"Get →", optional "Popular" tab `.idx-pop`).

Landing content (both fa/en) is fully filled in the file — Ukraine H1 «کانفیگ رایگان اوکراین» /
"Free Ukraine config", promise, 3 benefits, 3 SEO blocks, 4 FAQ; USA H1 «آیپی ثابت آمریکا» /
"USA static IP" similarly. A fixed `.devbar` toggles Ukraine/USA/index — omit in production.

---

## 5. CONTENT PAGES (Phase 5) — guides, FAQ, blog, about/contact, legal; container 1120px

Seven views (`v-*` devbar toggle → real routes). Datasets in `DATA{fa,en}`.

**5a. Guides index** (`/guides`) — page-head (book eyebrow, "Setup guides") + `.gcards` grid
(1→2→3 cols) of `.gcard`s: platform icon tile (android/apple/windows/apple/terminal) + name +
"Apps: {app}", an `.apps-mini` row (app icon + "Easy" metachip + "~3 min" metachip), and a
"View guide →" link. Platforms: Android/v2rayNG, iPhone/Streisand, Windows/Happ, macOS/Streisand,
Linux/Happ.

**5b. Guide detail** (`/guides/android` demo) — breadcrumb + H1 + chip-row (Easy · ~3 min ·
v2rayNG). `.doc` = sticky **TOC** `.toc` (220px, `sticky top:80px`, scroll-spy active state,
border-inline-start marker that flips RTL) + `.doc-main`: numbered `.stepcard`s each with a 16:9
labeled screenshot placeholder `.shot` (dashed) and (for the copy step) a config copy-field; a
"Troubleshooting" `.sub-h` + accordions; a **"Was this guide helpful?"** row `.helpful`
(Yes/No → `.voted` shows "Thanks for your feedback!"); prev/next platform links `.prevnext`.
Carries HowTo schema — keep steps semantically clean. 4 demo steps (install v2rayNG → copy link →
import from clipboard → connect).

**5c. FAQ** (`/faq`) — page-head (help eyebrow) + `.faq-tools` search input + category **tabs**
`.tabs` (All / Getting started / Volume & invites / Apps / Troubleshooting) + accordion list
`.faq-item` (data-cat, data-q) with client search+category filter and empty state
"No question matches that phrase." 8 demo Q/A across categories.

**5d. Blog index** (`/blog`) — tag tabs + a **featured post** `.feat` (`1.2fr 1fr` split, gradient
cover + tag + h2 + excerpt + meta) + `.bloggrid` (1→2→3) of `.post` cards. 4 demo posts
(v2rayNG guide, iPhone/Streisand, VLESS vs VMess, speed tips) with Persian dates («۱۹ تیر ۱۴۰۴»).

**5e. Post template** (`/blog/{slug}`) — breadcrumb + tag + H1 + meta row (team · date ·
read-time) + `.article-cover` (2:1 gradient) + `.prose` long-form (h2/p, LTR `.isl` islands) with
an **in-article CTA band** `.inline-cta` (dark, mini overlapping flags + "Get config" button)
inserted mid-article + related posts.

**5f. About + Contact** (`/about`, `/contact`) — `.two` split (`1fr 1.1fr` `≥860px`): left
`.mission` (lead + body + `.deflect` FAQ/guides links); right `.form-card` — topic `<select>`
(4 options), message `<textarea>` (the only validated field), optional reply-handle input, a
grad send button, response-time note. Success morph `.form-card.sent` → `.form-success` (check +
"Your message was sent"). Error `.field.err` shows `.errmsg` "Please write a message." **No email
addresses, no messenger/social links.**

**5g. Legal** (`/terms`, `/privacy`) — a Terms/Privacy pill switch `.legal-switch`, "Last updated"
line, `.doc` = sticky TOC + numbered `.legal-body` sections. Privacy contains a highlighted
**device-identity** note `.privacy-note` (brand-tint, shield): plainly explains the signed cookie +
light fingerprint, "not to identify you personally" — what we store vs never store (no name/email/
phone). 5 terms sections, 5 privacy sections, all quoted in the file.

---

## 6. MY STATUS + DEVICE TRANSFER (Phase 6, `/status`) — container 1080px

Device-identity based, **no login**. Model `CFG={usedMB:380, totalMB:1024, invitesDone:3,
invitesCap:10, remain:14h50m}`; active `LOC=Germany`; 4-row claim `HIST`; transfer `CODES`
(8-char, `XXXX-XXXX`); `notifPerm` ∈ default|granted|denied.

**Dashboard view** `viewDash`:
1. **Page head** — device eyebrow, H1 "My status" / «وضعیت من», and an **identity note**
   `.idnote` (device icon) "Your history lives on this browser." + link **"Move to another
   device"** (opens transfer modal).
2. **Stat row** `.grid-stats` (2→4 cols) of `.card.stat`:
   - Today's usage — a **mini ring** `.ring-mini` (44px SVG, percent center) + value +
     "· of 1 GB".
   - Time left — clock icon + live `hms` countdown (ticks 1s, tabular, LTR-isolated).
   - Daily volume — bolt icon + total.
   - Successful invites — users icon + `۳ / ۱۰`.
3. **Main grid** `.grid-main` (`1.35fr 1fr` `≥860px`): left = **active config card** `.cfg-card`
   (reuses Phase-1 S4 essentials: config-loc with "Active" + live "Online" pill, config
   copy-field, usage meter, actions: "Change location" secondary + three app icon-only buttons)
   + a **missions summary** `.msum` link card → `/rewards`. Right column = **claim history**
   `.hist` (rows: flag + name + date + status pill `.ok`/`.exp`) and **settings** `.settings`
   (Language mini-seg, Theme mini-seg, Notifications toggle `.switch` — permission-state-aware,
   disabled+`Blocked in browser` tag when denied, `Enabled` tag when granted).
4. **Danger row** `.danger-row` (danger-tinted) — "Reset this device's data" + desc + destructive
   button → confirm dialog.

**New-device view** `viewNew` (empty state): page-head, then main grid with a big **empty card**
("You haven't claimed a config yet" + "Get your first config" CTA) and a **restore/transfer-card**
`.transfer-card` ("Used GozarX before?" + code input `.code-input` (LTR, uppercase, letter-spaced)
+ "Restore history" button; wrong/expired → `.code-input.err` shows "Code is wrong or expired.").
Below: empty history card.

**Transfer modal** `#tmodal` (`.overlay` + `.modal`, pop animation) — three states
(`.state.on`):
- **Generated/waiting** `tm-gen`: header (device tile + "Move to another device"), sub, a big
  dashed **8-char code** `.bigcode` (26px, letter-spaced, LTR) + copy button, expiry line
  `.expiry` (clock + "Expires in" + live `mm:ss` countdown from 598s), plus demo "Sim: redeemed"
  / "Sim: expire" ghost buttons + note.
- **Redeemed-success** `tm-ok`: 60px success circle (check) + "Your history was moved!" + desc +
  "Got it".
- **Expired** `tm-exp`: 60px warning circle (clock) + "The code expired" + "…Generate a fresh
  one." + **"Generate a new code"** (cycles `CODES`, resets timer).
Reset dialog `#rmodal`: warning circle + "Are you sure?" + Cancel / "Yes, reset" (danger) →
switches to new-device view + toast "Device data reset."

Key copy: idnote «سوابق تو روی همین مرورگر ذخیره می‌شود.» / "Your history lives on this browser.";
tm_gen_sub, restore_err, restored «سوابقت بازیابی شد! ✨» / "Your history was restored! ✨" — all
quoted in the file. A `.devbar` toggles Dashboard/New device — omit in production.

---

## 7. PWA + SYSTEM STATES (Phase 7) — container 1080px

Config-driven reward chips `REWARDS={pwa:200, push:150}`. Cached config for offline
= Germany link. All surfaces rendered inside device "canvas" frames for review; extract the inner
components for the real app. Sub-nav `.subnav` (Install / Notifications / Offline / Errors /
Loading & toasts). A `reward-chip` = bolt + `+{n} MB`.

**7a. PWA install** — three surfaces:
- **Android/desktop soft prompt** `androidSheet` (dismissible bottom-sheet `.dock`): logo tile +
  "Install GozarX" / "Opens faster, full-screen, no browser bar." + **reward chip (+200 MB)** +
  actions "Later" (ghost) / "Install" (grow, download icon).
- **iOS Safari manual steps** `iosSteps` (illustrated, 3 numbered): 1 Tap the **Share** icon
  (share badge) → 2 Choose **"Add to Home Screen"** (plus badge) → 3 Tap "Add" — done! (check).
- **Installed state** `installedState`: 66px success tile + "GozarX is installed" + "…open it
  full-screen…" + reward chip + "Open app".
- A "Live preview" button opens the sheet in a real bottom-sheet overlay.

**7b. Push notifications**:
- **Pre-permission explainer** `pushExplainer` (sheet): bell header + "Turn on notifications" +
  "Only what matters — quietly." + 3 `.pitem` rows (Config ready / Volume running low /
  News & new locations, each icon+title+desc) + **reward chip (+150 MB)** + actions "Not now" /
  "Turn on" → then points at the native prompt.
- **Permission state cards** `stateCards` (3): **granted** ("Notifications on", ok/check, "Granted"
  tag), **dismissed** ("Not now", bell/mut, "Dismissed" tag), **blocked** ("Blocked in the
  browser", belloff/warn, "Blocked" tag) with an unblock `.hint` (per-browser: Chrome lock→
  Notifications→Allow; Safari Settings→Websites→Notifications).

**7c. Offline page** (`/offline`) `offlinePage` — `.sys`: wifi-off illustration, "Offline" code,
"No internet connection", "…Your last config is right here…", a **cached-config copy-field**
(last cached config, flag + name), "Try again" retry button.

**7d. Errors** — **404** `.sys`: ghost illustration, "Error 404", "This page wasn't found", a
**search input** `.sys-search`, and popular links (Get config / Locations / FAQ). **500 /
maintenance** `.sys`: wrench illustration (warning-ink), "Error 500", "One moment… something went
wrong", "That was on us, not you…", a **cta Retry** + secondary **FAQ** link. A note: maintenance
is the same page, calmer tone, **no external status links**.

**7e. Loading skeletons + toasts** — **hero skeleton** `skelHero` and **status skeleton**
`skelStatus` (shimmer `.skel` blocks using `--skel-1/--skel-2`); **toast stack** `toastStack`
showing an **app-update toast** ("A new version is ready" / "Refresh to get the latest version." +
Refresh button) and a success toast; demo buttons to fire each. Toast-position note reproduced
(top / inline-end; top-left fa, top-right en).

---

## 8. Copy: navigation, footer, shared (verbatim, fa / en)

| key | fa | en |
|---|---|---|
| nav_get | دریافت کانفیگ | Get config |
| nav_loc | لوکیشن‌ها | Locations |
| nav_more | حجم بیشتر | More volume |
| nav_guides | راهنما | Guides |
| nav_faq | سوالات | FAQ |
| nav_blog | وبلاگ | Blog |
| nav_status | وضعیت من | My status |
| ft_tag | کانفیگ آزمایشی رایگان روزانه، برای همه — بدون ثبت‌نام، سریع و ساده. | A free daily trial config for everyone — no signup, fast and simple. |
| ftc_product / resources / legal | محصول / منابع / قانونی | Product / Resources / Legal |
| ft_guides | راهنمای اتصال | Setup guides |
| ft_terms / ft_privacy / ft_contact | قوانین استفاده / حریم خصوصی / تماس با ما | Terms of use / Privacy / Contact |
| ft_copy | © ۱۴۰۴ GozarX — همهٔ حقوق محفوظ است. | © 2025 GozarX — All rights reserved. |
| trust4 (users stat) | +۱۲٬۰۰۰ کاربر | 12,000+ users |

Terminology consistency (sitewide, one term each): config = کانفیگ, volume = حجم,
invite = دعوت, location = لوکیشن. **Zero** login/signup/account/messenger/Telegram wording
anywhere.

---

## 9. Animations & interactions (reproduce)

- **CTA sheen** on hover (`@keyframes sheen`, 1.1s), press `scale(.985)`, trailing arrow slide
  (flips in RTL), success "morph" from spinner → check.
- **Countdowns** tick every 1s (`setInterval`), tabular, LTR-isolated, Persian digits in fa;
  segmented (widget) or inline `hms`/`ms` (status/transfer). Expiry timer 598s (10-min transfer).
- **Copy-to-clipboard**: `navigator.clipboard.writeText`, button → "Copied" + `.copied` class,
  revert ~1.4s.
- **QR** drawn on a canvas via deterministic PRNG; redraw on theme toggle & when panel opens.
- **Tabs/accordions**: toggle `data-open` / `aria-pressed`; chevron rotates 180° when open.
- **Scroll reveals** via IntersectionObserver (`.reveal → .in`); **scroll-spy** for TOCs; count-up
  for stats.
- **Web Share API** for invite/revive share (fallback toast). **PWA**: dismissible sheets, live
  overlays. **Locale/theme/platform** toggles fully re-render and swap dir/font/digits/copy.
- **Gauge / segmented / meter** fills animate (`.5–.6s ease`).
- All wrapped by `prefers-reduced-motion:reduce` → near-zero durations, reveals visible.

---

## 10. Assets manifest (already vendored under `frontend/site/public/`)

- **Flags** (circular SVG, viewBox 512, masked to circle): `flags/{ca,de,fr,gb,nl,tr,ua,us}.svg`.
  Selected by `emojiToCC`. Source also at `docs/website/design/assets/flags/`.
- **App icons**: `assets/apps/v2rayng.png` (192²), `streisand.webp`, `happ.webp` → `public/icons`.
  26×26 rounded, inset ring; gradient-initial fallback tiles as specified in §1.4.
- **Logo**: `logo-mark.svg` (inline symbol `#gz-logo`, two paths, ink + accent).
- **Fonts**: `fonts/YekanBakh-VF.woff2` (fa VF wght 100–950), `fonts/Inter-Variable-latin.woff2`.
- Existing Next scaffold already has matching component files under `frontend/site/components/`
  (ClaimWidget, CopyField, StatusView, TransferCard, ContactForm, FaqList, LegalArticle,
  RewardsTeaser, Header, Footer, PwaRegister, Turnstile, RetryButton) and routes under `app/`.

---

## 11. Fidelity-critical rules (do NOT deviate)

1. **CSS logical properties only** — no physical left/right anywhere. RTL is primary art
   direction, not a mirror afterthought.
2. **Flags are real circular SVGs derived from the remark emoji** (never emoji glyphs); match
   location→config by **remark name**, never index.
3. **Every config link / invite link / transfer code is an LTR monospace island**
   (`direction:ltr; unicode-bidi:isolate`) with a copy button — even inside RTL.
4. **Buttons must set `font-family:inherit`** or Persian falls back to Arial.
5. **No hardcoded economic numbers** — volume/hours/reward/cap all come from `site_*` settings;
   copy from the `content` table. Demo values here are placeholders only.
6. **App set is v2rayNG · Streisand · Happ** (NOT Hiddify), platform-ordered by UA detection.
7. **Persian digits** in fa copy (`۰۱۲۳`, `٫` decimal, `٬` thousands); technical strings stay
   Latin/LTR. Tabular numerals on all counters.
8. **Claim widget = 8 states + compact variant**, all designed; S3 & S6 (success & golden revive)
   are the fidelity-critical UX moments.
9. **Zero login/signup/account/Telegram/messenger** anywhere; surface the "no signup" promise
   proudly. Support only via the Contact page (no email/social).
10. **Theme**: follow system, manual toggle wins, mirror host `<html data-theme>` via
    MutationObserver; every text/bg pair passes WCAG AA in both themes.
11. **Gradients & radial decorations mirror angle in RTL**; directional icons flip, symmetric
    icons never; progress/steppers/gauges run inline-start→inline-end.
12. **Toast stack** = top / inline-end (top-left fa, top-right en), below the sticky header.
13. Remove the review-only `.devbar` platform/page toggles in production.
14. Responsive matrix: usable at 360 / 768 / 1280 with **no horizontal scroll**; hero widget
    above the fold at 360px; hit-targets ≥44px on mobile.
</content>
</invoke>
