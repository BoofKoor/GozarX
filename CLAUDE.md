# CLAUDE.md — Gozar v2

## What this is
A Telegram bot that gives each user a free **daily trial VPN config** from a Remnawave panel.
Users pick a language, claim one trial config per day for a chosen location, and grow their daily
traffic allowance by inviting friends. An RTL (Persian) React admin panel manages settings, content,
users, and broadcasts. Everything is Dockerized and installs near zero-touch.

## Architecture (fixed — do not change without asking)
- **One ASGI process:** aiogram 3 (Router + FSM) on **webhook**, fed by a **FastAPI** app under
  uvicorn (`--factory --proxy-headers`, behind nginx). FastAPI hosts:
  - `POST /tg/{secret}` — verify the secret path segment **and** Telegram's
    `X-Telegram-Bot-Api-Secret-Token` header, then `dp.feed_update(...)`.
  - `POST /panel-webhook` — Remnawave user events (expired / limited).
  - `/api/...` — admin REST API (JWT).
  - `GET /health`.
- **arq worker:** a separate process/container for broadcasts, forwards, and the pg_dump backup cron.
- **Remnawave** panel via API token (Bearer). One shared `httpx.AsyncClient`; TLS verification **on**.
- **PostgreSQL** + SQLAlchemy 2 async + Alembic. **Redis** for aiogram FSM, content/settings cache,
  and the arq queue.
- **nginx** terminates TLS (a **Cloudflare Origin Certificate** installed by the Phase 9 installer),
  routes `/api` + the webhooks to the app, and serves the SPA static build.
- **Runtime config lives in the DB** (`settings` / `content` tables), edited from the panel —
  changing it never needs a redeploy. Only secrets/infra are env vars.

## Layout & layering
Import package is `gozar` (under `backend/`). Imports flow **one direction only**:
`web/` + `bot/` (delivery) → `services/` (logic) → `db/repositories` + `remnawave/` + `cache/` (infra)
→ `config/`. Services never import delivery code, so the arq worker reuses logic without pulling in
FastAPI/aiogram. The boot sequence (`docker/entrypoint.sh`) is stable forever:
`alembic upgrade head` → `python -m gozar.seed` → `uvicorn gozar.web.app:create_app --factory`.

## Conventions (non-negotiable)
- Python 3.12, **async throughout**. **Logging only — never `print()` (ruff T201). Never log tokens or
  full payloads.**
- **Zero import side effects.** Config via `get_settings()` (lru_cache); never instantiate settings or
  touch DB/network at import time. Secrets are `SecretStr`.
- **All DB access through repositories.** One middleware opens **a single AsyncSession per update**
  and injects the loaded user + repos; handlers never open their own session and never re-query the
  same user twice.
- **Callback data is namespaced, matched by exact prefix** (`config:open`, `loc:pick:3`, `menu:back`).
  Never unanchored substring regex.
- **User-facing copy comes from the `content` table** via `content.text(key, lang, **tokens)`;
  placeholders are `{token}`, substituted only when provided. Never `str.replace` on message text.
- **Fixed UI chrome (button labels)** lives in a small **in-code i18n map**, not the DB.
- **Match a chosen location to its config by remark NAME, not list index.**
- **No process-global mutable state for per-user data** — per-user state in FSM/DB; shared caches in
  Redis, keyed properly.
- **Panel calls are single, bounded attempts** — log and move on; never `while result is None: retry`.
- **Broadcasts run in the arq worker**, never inside a handler. A broadcast removes a user **only** on
  a genuine "bot blocked / deactivated" error — never on transient failures.
- **Admin multi-step flows use aiogram FSM (Redis)**, never a module-global dict.
- **Use the configured referral reward everywhere** — never hardcode reward/cap numbers.
- **Remnawave: VERIFY every endpoint** against the live OpenAPI (`{PANEL_BASE_URL}/api`) before wiring;
  mark each with `# VERIFY:` and provide fallbacks rather than hardcoding response field names.

## Lessons from v1 (bugs designed out — see conventions above)
1. No destructive side effects on import (old `config.py` ran `delete_user()` + `create_tables()`).
2. No process-global mutable per-user state (old global location list → race → wrong config).
3. Match location → config by remark NAME, not `links[index]`.
4. No mass-deletion on errors (broadcast removes a user only on blocked/deactivated, never transient).
5. No unbounded panel retry loops (old `while result is None: retry` hung when the panel was down).
6. Derive locations from the trial squad, not a hardcoded "template user".
7. Admin multi-step flows in aiogram FSM, not a module-global dict.
8. Use the configured referral reward everywhere (old status screen hardcoded ×100).
9. Broadcasts in the arq worker, so the bot stays responsive on webhook.
10. Reminders via Remnawave webhook events, not by parsing `#Expired`/`#Limited` text from a channel.

## Data model
- `users`: telegram_id (PK bigint) · status enum(available/active_config/banned) · language enum ·
  referral_count · panel_username · reminder_enabled bool · referred_by bigint · created_at tz ·
  last_claim_at tz (provision time — the rolling-cooldown anchor, aligned with the trial's expiry).
- `config_logs`: id · user_id FK · location · created_at tz (one row per claim).
- `content`: unique (key, language) → body text. Editable bot copy, plus the website's `site_*`
  keys. A `site_copy_<designKey>` row OVERRIDES that key in the site's in-code `DESIGN_COPY`; a
  blank row means "use the in-code copy", so clearing a field in the panel restores the default
  rather than blanking the live page. The writable set is allowlisted in `services/site_copy_keys`.
- `settings`: key → value string. Runtime values (trial squad, locations, daily_limit_mb,
  referral_reward_mb, referral_reward_limit, trial_hours, ads_enabled, configs_per_page,
  ad_button_enabled/ad_button_text/ad_button_url/ad_button_emoji_id — the Persian-only promo button
  beside "change location" on the delivered config) — set via the first-run wizard, editable from
  the panel. NOT env vars.
- `site_push_logs`: one row per website Web-Push broadcast (title/body/url/locale · status ·
  recipients/sent/failed/pruned · created_at/finished_at). Written at ENQUEUE time by the route and
  completed by the arq worker — the fan-out is async, so without the row a broadcast that never ran
  would vanish silently instead of showing as stuck on `queued`.
- `site_faq_items`: the public site's FAQ (locale · category · question · answer · position ·
  published), unique on (locale, question). The site used to compile these 16 strings into its
  bundle, so a new recurring question cost a redeploy. Defaults are seeded from `seed_faq` on boot
  (`add_default`, never clobbering an edit) so the panel opens showing exactly what the site shows;
  the site keeps its in-code `FAQ_ITEMS` as the fallback for an empty/unreachable response.
- `broadcast_logs`: one row per panel-composed Telegram broadcast (body · languages · the two
  audience refinements · buttons JSON · status · recipients/sent/failed/**removed** ·
  scheduled_for/created_at/finished_at). Written at ENQUEUE time by the route and completed by the
  arq worker — the fan-out is async, so without the row a broadcast that never ran would vanish
  instead of showing as stuck on `queued`. `removed` is its own column, never folded into `failed`:
  a user is dropped ONLY on blocked/deactivated, and that distinction has to be visible to be
  trusted. Mirrors `site_push_logs` on purpose — two broadcast surfaces that report differently
  would be two things to learn.
- `broadcast_drafts`: a broadcast written and not yet sent (title derived from the body · body ·
  languages · the two audience refinements · buttons JSON · `send_hour` · created/updated). In the
  DB rather than the browser because the console is SHARED — one person drafts an announcement and
  another sends it, and a draft in `localStorage` is invisible to every tab but the one that typed
  it. Deliberately not a `broadcast_logs` row with a `draft` status: a log records something that
  happened and is never edited, a draft is mutable until it stops being one, and folding them
  together would make every history query responsible for excluding the unsent. `send_hour` is an
  hour, not an instant — an absolute time saved on Monday is in the past by Tuesday.
- `site_devices.last_seen_at`: the site's ONLY visit signal, refreshed by `current_device` on every
  identity-bearing request (throttled to once an hour, so a page load is not a row write). Without
  it every website figure was claim-derived plus an all-time "identities minted" counter — and that
  counter is not traffic: a cookieless client mints a fresh row per request, so it only grows and
  drags the conversion rate down with it.

## Reporting conventions
- **Display days are LOCAL days** (`gozar/config/reporting.DISPLAY_TZ`, Asia/Tehran) — `start_of_today`,
  `window_start`, `day_keys`, and every `date(timezone(tz, …))` bucket. A UTC midnight rolled the
  operator's counters over 3.5 hours early. This is display only: the claim cooldown is a rolling
  window anchored on `last_claim_at` and is deliberately untouched.
- **A range control must move every KPI under it.** Windowed figures carry the same figure over the
  previous, equal-length window (`Metric`); anything genuinely lifetime is named `*_all_time` and
  labelled as such, never mixed silently into the same row.
- **Don't report a status column as if it were live state.** `active_config` is healed by the panel
  webhook or the 15-minute reconcile sweep, and the sweep skips a device when the panel is
  unreachable — so it is split into live vs stale (`active_config_split`) rather than overstated.
- **A capped list says what it hid** (`locations_total` next to a top-10), or it reads as the whole
  picture.

## Dev workflow
- Deps via **uv** (`uv sync`, `uv add <pkg>`). Lint/format with **ruff**; gate every change with
  `ruff check`, `python -m py_compile` / `pyflakes` before committing.
- Migrations via Alembic (`make migrate` to autogenerate, `make upgrade`). The app entrypoint runs
  `alembic upgrade head` → `python -m gozar.seed` → uvicorn on boot.
- Run locally with `docker compose up` from a filled `.env` (copy `.env.example`).
- **One feature branch + one PR per phase**; keep each PR independently reviewable.
- **Re-read this file at the start of every session. Plan → confirm → implement.**

## Deployment (server, live test)
Production lives at **`https://gozarx.gozarxservices.com`**. After a phase is merged to `main`, the
owner deploys + smoke-checks on the server with (TLS overlay `docker-compose.tls.yml` is generated by
the Phase 9 installer and lives only on the server):
```bash
cd ~/GozarX
git checkout main && git pull origin main
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.tls.yml restart nginx
sleep 8
curl -sS -o /dev/null -w "%{http_code}\n" https://gozarx.gozarxservices.com/health   # expect 200
```
When a change needs a server deploy, hand the owner exactly these commands. The admin panel
(`/api/admin/*`) needs `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH` / `ADMIN_JWT_SECRET` in `.env`
(installer-generated; mint the hash with `python -m gozar.web.auth.passwords`).

**First-time install (server):** clone the repo, then `sudo ./install.sh` (or `make install`). It
prompts for the **domain first, then a TLS certificate** (Cloudflare Origin Certificate — cert + key),
collects the Telegram/panel/admin details, generates all secrets, writes a chmod-600 `.env`, builds +
starts the stack behind TLS (`docker-compose.tls.yml` + `nginx/nginx.tls.conf`, both server-only and
git-ignored), and verifies health, admin login, and the Telegram webhook. Re-running is safe — secrets
and the Postgres password are reused, never rotated. In Cloudflare: the DNS record must be **Proxied**
(orange cloud) and SSL/TLS mode **Full (strict)**.

## Build phases
0 Skeleton + this file + settings + logging + compose + .env.example; app boots `/health`.
1 DB models + Alembic initial migration + repositories.
2 Remnawave client (VERIFY markers) + content/settings service (Redis-cached) + seed.
3 Bot core on webhook: dispatcher + middleware + i18n + keyboards + /start + language + menu nav.
4 Core flow: trial provisioning + config claim + location picker + change location + status.
5 Referral + settings (language/reminder) + reminders via Remnawave webhook receiver.
6 Admin (FSM): stats, broadcast/forward (arq worker), ban, reset limits, refresh locations.
7 Admin API (JWT) + React/TS RTL panel: first-run setup wizard, dashboard, users/content/broadcast.
8 DB backup job (arq cron: pg_dump → Telegram channel). Tests: location matching, referral cap, content render.
9 Zero-touch installer (install.sh): Docker bootstrap, Cloudflare Origin-cert TLS, secret generation, compose up, health/login/webhook verify.
10 Panel rebuild: design tokens + UI kit + app shell; retention/period-comparison metrics; website
  section fixed (shared location validation, surfaced API errors, windowed analytics) and extended
  (device browser, push targeting + history, editable site copy, inbox tools, landing editor).
11 Website stats made honest (`site_devices.last_seen_at` visit signal, windowed KPIs with
  previous-period deltas, local-day boundaries, live-vs-stale active configs) + editable FAQ
  (`site_faq_items`, seeded from the site's in-code list).
12 Panel redesign, foundation: the Nocturne palette in `tokens.css`, the icon-rail shell, the three
  hand-drawn SVG charts (`HeroSparkline`/`AreaTrend`/`RadarRates`), and the fa/en i18n layer.
  Pages keep their current markup and migrate their strings as each is rebuilt.
13 Dashboard overview rebuilt on the new charts + fully bilingual; activation metrics WINDOWED
  (`median_hours_to_claim` / `activation_24h` become `Metric`s with a previous-window twin, so the
  range control moves them instead of sitting above frozen all-time figures).
14 The remaining pages rebuilt and migrated: users (avatars + `RecordDialog`), broadcast (reach
  breakdown, pre-flight, chat-frame preview), texts (grouped keys + per-key translation gaps),
  buttons, settings, system, login, both wizards, and all ten website pages. Every user-facing
  literal now lives in `messages.ts` — `i18n/no-literals.test.ts` fails the build on a new one.
  The bot's own location writes gain the squad validation the website side already had.
15 The panel measured against the approved artifact (`docs/panel/panel-redesign.html`) and closed
  to it. The console becomes two panels on a tinted ground with the page title in the top bar;
  dialogs portal out of the shell's containing block; both hand-drawn charts fill their column;
  cards drop their border and tables sit flush; `--surface-raised` and the primary button get
  per-theme values. Users gains a location filter, a filtered CSV export and a record card carrying
  the person's claim history and live traffic; broadcast gains audience refinements, inline buttons,
  scheduling and `broadcast_logs` — each needed API built rather than the design trimmed to fit.
  `docs/panel/shot.py` replaces the raw-chromium capture recipe, which could not render below
  ~500 CSS px and could not capture a recharts chart at all.
16 The panel measured against the artifact numerically rather than by eye, and closed on the
  remaining gap: the side panel's type hierarchy rebuilt on the design's own sizes, the console's
  ground gap and both panel radii corrected, the sub-nav band trimmed, the broadcast page brought
  back to the reference's density (four-line composer, chips without a reserved tick, the hour strip
  always visible) and given `broadcast_drafts`, and the users table switched to the reference's
  columns — lifetime claims and last-claim recency instead of panel username and signup date.

## Admin panel conventions
- **The panel has its OWN palette, "Nocturne"** — a deep indigo canvas with periwinkle brand blue —
  and deliberately does NOT mirror `docs/website/design/TOKENS.css`. An operator console is a dense,
  long-session tool and wants a calmer ground than a marketing page; the site keeps its own tokens.
  Every colour still resolves through a CSS custom property in `frontend/admin/src/styles/
  tokens.css`; components name a ROLE (`bg-surface`, `text-content-muted`, `border-line`) and the
  theme resolves it. Do not add `dark:` twins for base colours, and never hardcode a hex — charts
  read the same tokens via `lib/chartTheme`.
- **The panel is bilingual (fa/en).** No user-facing literal lives in a component: strings go in
  `src/i18n/messages.ts` and are read with `useI18n().t(key)`. The English map is typed against the
  Persian one, so a missing translation fails `tsc` rather than shipping. Direction follows the
  locale — use logical properties (`ms-`/`me-`, `start`/`end`, `border-s`), never `left`/`right`.
  Numbers and dates go through `lib/format`, which reads the active locale; never call
  `Intl.NumberFormat("fa-IR")` in a component.
- **Isolate every foreign-script run** (`unicode-bidi: isolate`): a Latin handle, a `⌘K`, a
  `sent / total` ratio or a `https://` inside a Persian sentence all reorder without it. Reach for
  `direction: ltr` only on a genuinely Latin run, and never on a block — it moves the text to the
  left edge as well.
- **An isolate is not enough for a slash- or dot-separated PAIR.** «۱۳۸ / ۴٬۰۹۶» renders as
  «۴٬۰۹۶ / ۱۳۸» under an RTL base direction even inside an isolate, because the two numbers are
  separate runs reordered by the base level — the character counter read as if the message were
  over the limit, and a `0.5 · 0.6` load average silently transposed its two figures. Such a pair
  needs `dir="ltr"` on its own inline span. Two measurements that must not mix (a percentage beside
  its `2.8 GB / 7.5 GB` hint) belong in separate FLEX ITEMS, not one inline run.
- **A "<number> <LATIN UNIT>" string carries its own isolate.** `formatMb`/`humanBytes`/
  `humanUptime` wrap their result in FSI…PDI (`\u2068`…`\u2069`), because they are plain functions
  whose output lands inside Persian sentences at ~40 call sites — «۱ GB» rendered as «GB ۱», the
  unit ahead of the number it measures. Wrap the value, not each call site.
- **A nested card RISES off its panel, it does not sink into it.** `bg-surface-raised` (#383D7A
  dark) is the design's own depth order: rail < content well < card < nested plate. Reserve
  `bg-surface-sunken` for things that genuinely recede — a progress TRACK, the content well, a
  form container, a preview frame, a zero-value heatmap cell. Inverting the two is what made the
  console read as flatter than the design.
- **Number glyphs stop at the digits, but the SEPARATOR counts too.** `localizeDigits` maps a
  decimal point between two digits to «٫», because `Intl` already does and a hand-built «۳.۱ TB»
  beside a «۳۷٫۵٪» used two marks for one idea. And recharts prints raw numbers, so `axisProps`
  carries a `tickFormatter` — without it every value axis was Latin under a Persian page.
- **Tailwind opacity modifiers are multiples of 5.** `bg-brand/12` and `bg-chart-1/18` are not on
  the scale and compile to NOTHING — silently, so a tinted badge just renders with no background.
  Use `/15`, `/20`, or the arbitrary form `bg-brand/[0.12]`. And a colour must exist in
  `tailwind.config.js` before a class can name it: `bg-chart-2` needs the `chart` ramp registered
  there, not only in `tokens.css`.
- **The three hero charts are hand-drawn SVG** (`components/charts/`), not recharts: masked fades
  and the radar's eight-point curve are not expressible there. recharts stays for ordinary bar and
  line charts. A fade means "this continues beyond the frame" — never fade a marker or a
  measurement. The path maths lives in `charts/geometry.ts` and is unit-tested.
- **A plot's y-scale comes from its TICKS, not its data.** `ticksFor` rounds the ceiling UP to a
  round number, so a chart that instead scales to `max(values)` pins the tallest curve to the top
  edge and puts the top gridline — and its label — off the canvas entirely. Pick the STEP from a
  round ladder and make the ceiling four of them; rounding the ceiling and quartering it labelled a
  300-high chart ۷۵ / ۱۵۰ / ۲۲۵.
- **A marker band is CLIPPED to the region under the curve**, so the curve is its top edge and it
  runs to the frame's floor. Drawn as a plain rounded rect from the marker down it becomes a
  lozenge floating under the dot. The clip region must reach the frame's SIDES too (`underCurve`,
  not `areaFrom`) — closed at the first and last data point, its diagonal slices the band into a
  teardrop whenever the marked day sits at either end.
- **`inset-inline-start` resolves against the element's OWN `dir`.** A time axis is a physical LTR
  space, so its hover readout is positioned inside an LTR wrapper and the RTL text lives one level
  in; marking the positioned element itself `dir="rtl"` sends it to the opposite edge of the chart.
- **One control per concern.** Form fields go through `<Field>` (label + hint + error + aria);
  inputs through the kit (`Input`/`Textarea`/`Select`/`Switch`/`Checkbox`/`NumberInput`). Never
  hand-write an input class string — `.field-control` is the single definition.
- **Every page starts with `<PageHeader>`**; a section's sub-navigation is `NavTabs`, a range/filter
  choice is `Segmented`, a record detail is `RecordDialog` (a centred, backdrop-blurred modal — a
  record is something you look AT, not a sidebar that slides out), a "nothing here" is `EmptyState`
  and a failed query is `ErrorState` (never the empty state — the two need opposite responses).
- **Surface the server's reason.** Mutation `onError` uses `apiErrorMessage(err, fallback)`; a 400
  naming an unserved location, a 409 and a 502 must not collapse into one generic toast.
- **A range control drives every windowed query on its page** — not just the chart next to it.
- **Admin-authored HTML is sanitised before preview** (`lib/sanitize`): the panel origin holds the
  JWTs, so a pasted `<img onerror=…>` must never execute there even when the row is trusted content.
- **All four location writers validate against their squad** through
  `web/routes/admin/site_locations` — matched by remark NAME, never an index. That is the website's
  settings PUT and wizard, and the BOT's settings PUT and wizard: a name the squad does not serve is
  offered in a picker and then matches no remark, so the claim dead-ends. Validation is best-effort
  by design — with no squad set, or the panel unreachable, the admin's value is stored rather than
  the admin locked out. The panel drives the same choice through the shared `<LocationPicker>`.
- **A modal surface owes the keyboard four things**, and they live in ONE place (`useFocusTrap`):
  Esc closes · focus moves in and is restored on exit · Tab cycles inside · background scroll locks.
  A dialog also needs a NAME — `role="dialog"` without `aria-labelledby` announces "dialog" and
  nothing else. And a drawer that stays mounted to animate must be `inert` while closed, not merely
  `aria-hidden` + `pointer-events-none`: those stop the mouse and the screen reader but leave every
  link inside in the tab order (nine of them, on a phone, before the page).
- **A row that opens something is a control.** `<TR onClick>` gives it `tabIndex`, `role="button"`,
  Enter/Space and a `label` naming the record — without them the whole table is mouse-only, which
  on Users and Devices meant no record could be opened by keyboard at all.
- **Don't gate focusability on layout.** `offsetParent` is null for any `position: fixed` element —
  which every dialog panel is — and for everything under jsdom, where it silently empties the
  focusable list and makes the trap untestable. Read hidden-ness from attributes.
- **A missing translation fails `tsc`; a literal that never reached the catalogue fails a TEST.**
  `i18n/no-literals.test.ts` walks the source for Persian outside `messages.ts`, `lib/format` (which
  owns the locale tables) and comments. Adding to its allowlist needs a reason that is not "this one
  is fine". It only looks for PERSIAN, so an English literal (`"ok"`, `"down"`) slips past it — the
  English map being typed against the Persian one is what catches those, but only once the string
  is a key at all.
- **`fixed inset-0` means the viewport only until an ancestor has a transform.** The shell's entry
  animation ends on `transform: translateY(0)` with `animation-fill-mode: both`, so it keeps a
  computed `matrix(1,0,0,1,0,0)` forever and becomes the containing block for every fixed
  descendant. Measured: a record dialog centred inside the 1180px content column instead of the
  window, its backdrop stopping at that column's edges, its panel 229px below the fold, and
  `max-h-full` measuring 1557px so it never scrolled to its own footer. `Modal` and `RecordDialog`
  portal to `<body>`; anything else full-screen must too. A filter or `contain` on an ancestor does
  the same thing.
- **Measure the artifact, do not eyeball it.** Pinning the artifact's `.mock` to the panel's viewport
  width and probing both with ONE script is what separates a real gap from a felt one. It found the
  panel's three dashboard bands within 1–3% of the design's (218/399/119 vs 224/401/119) and its
  content type histogram nearly identical — so the composition was never the problem — while the
  same run showed the console's own gap/padding at 12px against 14.4, both panels at a 16px radius
  against 14, and the side panel with 45% of its text runs at ONE size where the design spreads nine.
  "It doesn't feel like the reference" is a measurable claim.
- **Size a dense panel off the DESIGN's numbers, not Tailwind's ladder.** `text-lg` over `text-sm`
  put an 18px figure above a 14px label where the design has 1.4rem over 0.8rem over 0.585rem: the
  number shrank and the label grew, so the hierarchy was compressed from both ends and the figure
  stopped being the thing you read. Arbitrary values are correct here — the ladder is a convenience,
  not the spec. Same for boxes: `SideHead` as `text-sm pt-2 pb-1` was a 32px box for the design's 23.
- **A label wraps; a caption gives way.** The design puts `line-height: 1.4` on the gauge label
  precisely because it can run to two lines. Truncated instead, English "Online users" lost its
  second word to a caption beside it that was merely longer. Whatever is primary in a row must not
  be the thing that clips.
- **A copy string can outlive the limitation it describes.** «زمان‌بندی هنوز در سرور پیاده نشده» sat
  under the hour strip for a whole release after scheduling shipped, telling operators the feature
  they were using did not exist. When a phase removes a limitation, grep the catalogue for the
  sentence that announced it.
- **A scrollable flex COLUMN does not overflow — it SQUEEZES.** Its children keep the default
  `flex-shrink: 1`, so content taller than the box is absorbed rather than scrolled, and
  `overflow-y: auto` is then handed nothing to scroll. Text children resist (their content is their
  floor); an SVG has no floor, so the ENTIRE shortfall lands on the one child that cannot object.
  Measured on a 650px-tall window: the side panel's radar drew 280×35 against a natural 209 while
  `scrollHeight === clientHeight`, which is the panel reported as "static, no scroll" AND the chart
  reported as broken — one cause, two bug reports. Any `flex-col` + `overflow-y-auto` needs
  `[&>*]:shrink-0`. It also hides at desk height: at a 1000px viewport the same panel is perfect,
  so verifying only at 1440×1000 proves nothing about a laptop.
- **A panel placed twice needs its geometry defined ONCE** (`SIDE_STACK`/`SIDE_WIDTH` in
  `layout/chrome`). The side panel's below-`xl` copy was a bare `<div>`: no gap between any of its
  nine children, and a 340×254 chart drawn 968 wide — therefore 723 TALL, one tile higher than the
  viewport. A width-driven SVG is safe only while its aspect is wide; a near-square one needs a
  bound or "fill the column" and "stay a sane height" stop being the same instruction.
- **`overflow-x: auto` makes the OTHER axis scroll too.** When one axis is not `visible` the other
  computes from `visible` to `auto`, so a horizontal tab strip that exceeds its own content box by a
  single pixel becomes a VERTICAL scroll container — invisible under overlay scrollbars, a stubby
  arrowed scrollbar beside the tabs on Windows. `Tabs` earned that pixel by carrying the underline
  overlap (`-mb-px`) on each TAB instead of on the strip, which shortened the strip's content box to
  1px less than the tabs standing in it and clipped the active 2px underline to 1px as well.
  `NavTabs` already put it on the strip. Name the axis you do not want (`overflow-y-hidden`) and put
  a negative margin meant for the strip ON the strip.
- **An SVG with a viewBox and a FIXED height letterboxes.** `preserveAspectRatio` scales uniformly
  and centres the remainder, so `viewBox="0 0 900 292"` in an 852×240 box drew 740 wide with ~56px
  of dead space on each side — the trend aligned with neither the KPI band above it nor the cards
  below, and the hero sparkline stopped short of the tile edges its negative margins exist to
  reach. Charts are width-driven with `h-auto`. `preserveAspectRatio="none"` is only safe where
  there is no text and no round marker to distort (`MiniTrend`).
- **A value axis needs room for the LOCALE's digits.** `YAxis width={32}` with `margin.left:-16`
  leaves 16px; a three-digit Persian tick needs ~24, so «۴۰۰» rendered as «۰۰» on every recharts
  chart — silently. `Y_AXIS_WIDTH` and `CHART_MARGIN` live in `lib/chartTheme` so the next chart
  inherits the room.
- **recharts animates in JAVASCRIPT, so `prefers-reduced-motion` never reaches it.** `index.css`
  honours the query for CSS only; react-smooth grows a clip rect from zero width with
  `requestAnimationFrame`. Two consequences: a console full of moving charts for an operator who
  asked for stillness, and — because that animation only advances on real frames — a chart that
  screenshots as an EMPTY GRID, geometry present in the DOM and nothing painted. Spread
  `useSeriesAnimation()` onto every `<Area>`/`<Line>`/`<Bar>`/`<Pie>`.
- **A card has no border**, and a table is FLUSH in an unpadded card. The design separates a card
  from the well by its own SURFACE; a 1px `--line` ring around every panel is most of why the
  console read boxier and flatter than the design. And the table's header is a tinted band running
  the card's full width, which an inset table cannot draw — it floats with a gutter on each side and
  stops reading as the table's top edge. `<Card padded={false} className="overflow-hidden">`, and
  `rounded-card`/`p-card` so the table and the card footer bleed back by the same named amount.
- **`--surface-raised` must differ from `--surface` in BOTH themes.** It was `#FFFFFF` in light —
  byte-identical — so every nested plate in the light theme was invisible: both dashboard gauges,
  the traffic card, the whole service-health list and eighteen other sites.
- **The primary button is its own token (`bg-btn`), not the brand ramp.** The design keeps it
  periwinkle on the dark console and CHARCOAL on the light one, where a saturated blue button beside
  blue-tinted cards and a blue chart reads as one more chart element rather than the page's action.
- **The page title lives in the TOP BAR**, portalled there by `<PageHeader>`, which keeps only its
  actions in the page. Rendered in both places the console said its own name twice in a column and
  spent two horizontal bands before any content. A page with no shell around it (login, the wizards)
  falls back to drawing them in place.
- **A chevron that means "previous"/"next" mirrors with the reading direction** (`rtl:-scale-x-100`).
  Hardcoded for RTL, the English pager pointed "previous" forward and "next" back.
- **The count shown before a send and the list the worker walks are ONE query.** `count_audience` and
  `audience_ids` share `_audience`, so a filter cannot narrow the displayed figure without narrowing
  the fan-out. Banned users are excluded unconditionally — they can receive nothing, and counting
  them inflated every pre-flight number.

## Security
- TLS verification on for all panel calls. Installer auto-generates secrets; `.env` is chmod 600.
- Webhook protected by the secret path segment + Telegram secret_token header.
- Never log secrets or full update/panel payloads.
