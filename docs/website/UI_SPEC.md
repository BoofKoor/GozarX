# اسپک طراحی UI وب‌سایت GozarX — نسخهٔ ۱.۱

این سند، اسپک کامل و مرحله‌به‌مرحلهٔ طراحی رابط کاربری وب‌سایت GozarX است: یک **محصول مستقل از
بات تلگرام** (کانفیگ آزمایشی رایگان روزانه از پنل Remnawave، رشد حجم روزانه با دعوت دوستان) که
روی همان زیرساخت سوار می‌شود، با هدف سئوی قوی روی کلیدواژه‌های فارسی و تجربهٔ کاربری درجه‌یک
دوزبانه (fa/en، RTL/LTR کامل).

هر «فاز» یک پرامپت آمادهٔ کپی‌کردن برای Claude Design دارد + چک‌لیست پذیرش برای تأیید شما.
**تا فازی تأیید نشده، فاز بعدی شروع نمی‌شود.**

> تاریخچه: v1.0 → v1.1: جداسازی محصول سایت از بات (زیرساخت مشترک، کاربران و اقتصاد جدا با
> کلیدهای `site_*`) و حذف کامل تلگرام از UI سایت (جایگزین تداوم بین‌دستگاهی: «کد انتقال»).

---

## ۰) تصمیم‌های تأییدشده (مبنای کل سند)

| تصمیم | انتخاب نهایی |
|---|---|
| صفحهٔ اول | **ابزار دریافت = هیرو.** ویجت دریافت کانفیگ، خودِ هیروی صفحهٔ اصلی است (الگوی speedtest.net). بخش‌های معرفی/اعتماد/سئو زیر آن. |
| احراز هویت | **بدون لاگین، همیشه.** هویت دستگاه = کوکی امضاشدهٔ httpOnly + هش اثر انگشت مرورگر + آی‌پی، به‌علاوهٔ Cloudflare Turnstile نامرئی. تداوم بین‌دستگاه‌ها با «کد انتقال» یک‌بارمصرف (فاز ۶) — نه هیچ حسابی. |
| زبان و URL | **فارسی در ریشهٔ دامنه** (RTL)، انگلیسی زیر `‎/en/‎` (LTR). hreflang دوطرفه + x-default. هیچ ریدایرکت خودکار مبتنی بر IP؛ فقط بنر پیشنهاد تغییر زبان. |
| استک ساخت (بعد از UI) | **Next.js (App Router)** به‌صورت کانتینر جدا پشت همان nginx. سایت در ریشهٔ دامنه؛ پنل ادمین فعلی به `‎/admin‎` منتقل می‌شود. |
| سطح جدایی از بات | **زیرساخت مشترک، محصول جدا.** همان سرور/پنل Remnawave/دیتابیس/پنل ادمین (بخش جداگانهٔ «وب‌سایت»)، ولی کاربران سایت از کاربران بات کاملاً جدا نگهداری می‌شوند و اقتصاد سایت کلیدهای تنظیمات مخصوص خودش (`site_*`) را دارد. |
| تلگرام در سایت | **حذف کامل از UI.** هیچ لاگین/اتصال/ماموریت/تبلیغ تلگرامی در سایت وجود ندارد. (تصمیم v1.1 — جایگزین اتصال اختیاری تلگرامِ v1.0.) |

**واقعیت‌های محصول که طراحی باید به آن‌ها وفادار باشد** (منطق از همین ریپو reuse می‌شود):

- هر کاربر هر `site_trial_hours` ساعت (پیش‌فرض ۲۴) **یک** کانفیگ می‌گیرد؛ کول‌داون «چرخشی» است
  (از لحظهٔ آخرین دریافت)، نه نیمه‌شب.
- حجم روزانه = `site_daily_limit_mb` + `site_referral_reward_mb` به‌ازای هر دعوت موفق، تا سقف
  `site_referral_reward_limit` دعوت. **هیچ عددی در UI هاردکد نمی‌شود؛ همه از تنظیمات می‌آیند.**
- لوکیشن‌ها با «نام remark» شناخته می‌شوند (مثل `Germany 🇩🇪`) و لیستشان runtime است.
- کانفیگِ حجم‌تمام‌شده ولی زمان‌دار، با یک دعوت موفق **همان لحظه دوباره فعال می‌شود** (revive) —
  این یک لحظهٔ طلایی UX است و باید در طراحی دیده شود.
- حالت‌های خروجی دریافت (از سرویس trial): `Provisioned`، `AlreadyActive`، `AlreadyClaimedToday`
  (با زمان باقی‌مانده)، `NoLocations`، `NotReady`، `PanelError`. ویجت باید **همهٔ** این حالت‌ها را
  طراحی‌شده داشته باشد.

---

## ۱) پروتکل کار با Claude Design

1. در claude.ai یک Project بسازید و **بلوک CONTEXT** (بخش ۲) را در Project Instructions بگذارید
   (یا اول هر چت پیست کنید).
2. برای هر فاز یک چت جدید؛ فقط پرامپت همان فاز را بفرستید.
3. خروجی را با **چک‌لیست پذیرش** همان فاز بررسی کنید؛ اشکالات را در همان گفتگو اصلاح بخواهید.
4. بعد از تأیید فاز ۰، «بلوک نهایی CSS variables» را از Claude بگیرید و به انتهای Project
   Instructions اضافه کنید تا فازهای بعد به توکن‌های قطعی وفادار بمانند.
5. فایل HTML نهایی هر فاز را آرشیو کنید (`phase-0.html` … `phase-8.html`) — ورودی فاز ساخت.
6. فقط بعد از تأیید شما، سراغ فاز بعدی بروید.

**قوانین طلایی (برای هر فاز، بدون استثنا):**

- هر تحویل باید **هر دو زبان** (fa راست‌چین / en چپ‌چین)، **هر دو تم** (روشن/تاریک) و **دو سایز**
  (موبایل ~۳۶۰px و دسکتاپ ~۱۲۸۰px) را پوشش دهد — با سوئیچر داخل خود پیش‌نمایش.
- خروجی هر فاز: **یک فایل HTML خودکفا** (بدون منبع خارجی) با تولبار کوچک بالای صفحه برای
  تغییر زبان/جهت و تم. توکن‌ها به‌صورت CSS Custom Property تا در فاز ساخت مستقیم برداشته شوند.
- هر کامپوننت باید تمام حالت‌هایش را نشان دهد: default / hover / focus-visible / active /
  disabled / loading / error / empty.
- در پایان هر تحویل، Claude Design باید **خودآزمایی (self-audit)** را اجرا و گزارش کند:
  آینه‌بودن کامل RTL/LTR، کنتراست AA، ریتم فاصله‌گذاری روی گرید 4px، عدم سرریز افقی در ۳۶۰px.

---

## ۲) بلوک CONTEXT — اول هر پرامپت کپی شود

```text
=== GOZARX WEBSITE — DESIGN CONTEXT (paste before every phase prompt) ===

PRODUCT
GozarX is a standalone website that gives every visitor a FREE daily trial VPN config (V2Ray/VLESS
links). One config per rolling 24h window (configurable "trial_hours"). Daily allowance starts at
~1 GB (configurable) and grows by ~500 MB per successful friend invite, capped (all numbers
configurable — NEVER hardcode them in copy; render as dynamic values). Locations (e.g.
"Germany 🇩🇪", "Ukraine 🇺🇦") are dynamic strings with flag emojis. A config whose data ran out
(but time remains) is INSTANTLY revived when one invited friend claims — design celebrates this.
Identity is purely device-based (signed cookie + light fingerprint + invisible anti-bot check):
there is NO login, NO signup, NO email, NO phone number, and NO Telegram anywhere in the UI.
This "zero signup" promise is a core brand differentiator — surface it proudly.

AUDIENCE & LANGUAGES
Primary: Persian-speaking users (Iran), often on Android, often slow/filtered networks — fast,
light pages matter. Persian (fa, RTL) is the DEFAULT locale at the domain root; English (en, LTR)
lives under /en/. Every screen must be designed in BOTH directions — RTL is not a mirror
afterthought, it is the primary art direction.

BRAND & TONE
Name: "GozarX" (fa copy may use «گذر»). Tone: friendly, direct, trustworthy — no corporate
stiffness, no childish slang. Short sentences. Persian copy is written natively (not
translated-sounding).

COLOR TOKENS (CSS custom properties; light / dark)
--brand-50:#EFF6FF --brand-100:#DBEAFE --brand-200:#BFDBFE --brand-300:#93C5FD
--brand-400:#60A5FA --brand-500:#3B82F6 --brand-600:#2563EB --brand-700:#1D4ED8
--brand-800:#1E40AF --brand-900:#1E3A8A --brand-950:#172554
Primary action: brand-600 (light theme) / brand-500 (dark theme); hover one step darker/lighter.
Accent (gradients & highlights ONLY, never text): cyan #06B6D4;
hero gradient: linear-gradient(135deg,#2563EB,#06B6D4) — flip angle in RTL.
Success:#10B981 Warning:#F59E0B Danger:#EF4444 (each with a 100-tint surface for light theme and
a 950-ish translucent surface for dark theme).
Neutrals: slate scale. Light: bg #F8FAFC, surface #FFFFFF, border #E2E8F0, text #0F172A,
muted #64748B. Dark: bg #020617, surface #0F172A, raised #1E293B, border #334155(40%),
text #F1F5F9, muted #94A3B8.
All text must pass WCAG AA (4.5:1; 3:1 for ≥24px bold). Theme follows system, manual toggle wins.

TYPOGRAPHY
fa: "Vazirmatn" (400/500/700), digits in Persian form (۰۱۲۳) inside copy; technical strings
(config links, usernames, codes) always Latin digits and LTR-isolated. en: "Inter" (400/500/700).
Never letter-space Persian text. Numeric UI (counters, timers, usage) uses tabular numerals.
Scale (desktop / mobile, px): display 56/36 · h1 40/30 · h2 32/26 · h3 24/20 · h4 20/18 ·
body-lg 18/17 · body 16 · small 14 · caption 12. Line-height: fa body 1.8, fa headings 1.4;
en body 1.6, en headings 1.2. en headings letter-spacing -0.01em.

LAYOUT & SPACE
4px base grid — every margin/padding/gap is a multiple of 4. Section vertical padding:
96px desktop / 64px tablet / 48px mobile. Container: max-width 1200px, gutters 24px mobile /
32px desktop. 12-column grid on desktop. Cards radius 16px; buttons/inputs radius 12px;
hero claim card radius 24px; pills radius 9999px. Shadows: soft layered
(0 1px 2px rgba(2,6,23,.06), 0 8px 24px rgba(2,6,23,.08)); primary CTA gets a subtle blue glow.
Focus ring: 2px brand-500 outline + 2px offset, visible in both themes.

MOTION
Durations 150ms (hover) / 250ms (state) / 400ms (page-level), ease-out. Micro-interactions on the
claim button (press scale .98, success morph). Countdown digits tick smoothly. Respect
prefers-reduced-motion (fade-only fallbacks).

RTL/LTR RULES (hard requirements)
1. dir="rtl" on <html> for fa, dir="ltr" for en; fonts swap with locale.
2. CSS logical properties ONLY (margin-inline-start, padding-inline-end, inset-inline,
   text-align: start…). No physical left/right values anywhere.
3. Directional icons (arrows, chevrons, "next/back") flip in RTL; symmetric icons (shield, globe,
   download, QR) never flip. Progress bars & steppers run inline-start → inline-end.
4. Config links / URLs / codes render in dedicated LTR islands: dir="ltr" + unicode-bidi:isolate,
   monospace, with copy button. Mixed-direction lines (e.g. English location name inside a
   Persian sentence) wrap the foreign fragment in <bdi>.
5. fa copy uses Persian digits & Persian punctuation (،؛؟) and «guillemets»; en uses Latin.
6. Gradients/asymmetric decorations mirror their angle in RTL.

QUALITY BAR / DELIVERABLE
Each phase ships ONE self-contained HTML file (inline CSS/JS, no external assets; system font
fallbacks are fine in the preview) with a fixed mini-toolbar: locale toggle (fa/en — swaps dir,
font stack, and ALL copy) and theme toggle (light/dark). Show mobile (~360px) and desktop layouts.
Show every component state. Copy: write real, native microcopy in BOTH languages (placeholder
"lorem" is forbidden). End with a printed SELF-AUDIT: RTL mirroring ✓, AA contrast ✓, 4px rhythm ✓,
no horizontal scroll at 360px ✓, all states present ✓.
=== END CONTEXT ===
```

---

## ۳) معماری اطلاعات — نقشهٔ کامل سایت

مسیرهای فارسی در ریشه؛ نسخهٔ انگلیسی همان مسیر با پیشوند `‎/en‎`. اسلاگ‌ها انگلیسی می‌مانند
(پایداری URL و لینک‌سازی؛ کلیدواژهٔ فارسی از `title`/`h1`/محتوا می‌آید).

```
/                       صفحهٔ اصلی (هیرو = ویجت دریافت + بخش‌های معرفی)
/locations              فهرست لوکیشن‌ها (گرید کارت‌ها)
/location/{slug}        لندینگ سئو هر لوکیشن (ukraine, germany, usa-static-ip …) — ویجت با لوکیشن پیش‌انتخاب
/l/{slug}               لندینگ‌های کلیدواژه‌ای (free-v2ray-config, free-vpn-daily …) — ساخته‌شده از پنل ادمین
/rewards                «حجم بیشتر» — کارت‌های ماموریت (دعوت، PWA، اعلان، streak)
/invite/{code}          لینک دعوت (فرود → ویجت دریافت + ثبت referrer)
/status                 «وضعیت من» — داشبورد سبکِ مبتنی بر دستگاه (مصرف، تاریخچه، دعوت‌ها، انتقال دستگاه)
/guides                 راهنمای اتصال — فهرست پلتفرم‌ها
/guides/{platform}      android / ios / windows / macos / linux (اپ‌ها: v2rayNG، Hiddify، Streisand…)
/faq                    سوالات متداول (دسته‌بندی + جستجو)
/blog + /blog/{slug}    مقالات سئویی
/about  /contact        دربارهٔ ما / فرم تماس (بدون هیچ فیلد هویتی اجباری)
/terms  /privacy        قوانین / حریم خصوصی
/offline  /404  /500    صفحات سیستمی
```

ناوبری هدر: دریافت کانفیگ · لوکیشن‌ها · حجم بیشتر · راهنما · سوالات · وبلاگ | سوئیچر زبان · تم ·
دکمهٔ «وضعیت من».

---

## ۴) فازهای طراحی

### فاز ۰ — دیزاین سیستم (شیت توکن‌ها و کامپوننت‌های پایه)

**هدف:** زبان بصری قفل شود تا فازهای بعد فقط «صفحه‌چینی» باشند.

**پرامپت:**

```text
PHASE 0 — DESIGN SYSTEM SPECIMEN

Using the GozarX CONTEXT above, build a single-page design-system specimen:

1. Color plate: full brand scale + semantic colors + neutrals, rendered in both themes, each
   swatch labeled with its token name and hex, with an AA-contrast badge on text/background pairs.
2. Typography specimen: full type scale in BOTH locales side by side (fa Vazirmatn-style RTL,
   en Inter-style LTR), including a mixed-direction paragraph (a Persian sentence containing
   "Germany 🇩🇪" and a vless:// link rendered as an LTR island) and Persian vs Latin digits.
3. Spacing & radius scale: visual ruler of the 4px rhythm, section paddings, container widths,
   radius set.
4. Core components, every state (default/hover/focus-visible/active/disabled/loading):
   buttons (primary, secondary, ghost, destructive; sizes md/lg; with leading icon),
   inputs (text, select, search; with error + helper text), badge/chip, tooltip, toast (success/
   error/info), modal + bottom-sheet (mobile), tabs, accordion item, skeleton loader, progress
   (linear bar + circular ring), countdown timer (HH:MM:SS, tabular), stat tile, card (flat +
   interactive), pill-style location chip with flag emoji + selected state, copy-field (LTR
   monospace island with copy button + "copied" feedback), QR code placeholder block, stepper
   (3 steps, direction-aware), language switcher, theme toggle.
5. Icon direction table: which icons flip in RTL (arrows, chevrons, send) vs never flip (shield,
   globe, download, QR, check).
Deliver per the QUALITY BAR (one HTML file, locale+theme toolbar, self-audit printed at the end).
```

**چک‌لیست پذیرش:**
- [ ] آبی اصلی #2563EB است و روی هر دو تم، متن/پس‌زمینه‌ها AA پاس می‌کنند (بج‌ها را ببینید).
- [ ] با سوئیچ fa↔en، جهت، فونت، اعداد (۱۲۳↔123) و علائم نگارشی همه عوض می‌شوند.
- [ ] پاراگراف مخلوط: لینک `vless://` حتی وسط جملهٔ فارسی، LTR و تمیز است.
- [ ] همهٔ کامپوننت‌ها همهٔ حالت‌ها را دارند؛ focus-visible در هر دو تم دیده می‌شود.
- [ ] هیچ margin/padding خارج از مضرب 4px نیست (گزارش self-audit).

---

### فاز ۱ — ویجت دریافت کانفیگ (قلب محصول)

**هدف:** طراحی کامل ویجت claim با **تمام** حالت‌های واقعی بک‌اند. این مهم‌ترین فاز است؛ وقت
بیشتری برایش بگذارید و تا بی‌نقص نشده تأیید نکنید.

**پرامپت:**

```text
PHASE 1 — THE CLAIM WIDGET (hero tool)

Using the GozarX CONTEXT (and the approved Phase 0 system), design the claim widget as a large
elevated card (radius 24) that will sit as the homepage hero. Show it standalone on a hero-like
gradient backdrop, mobile and desktop, both locales, both themes. Design ALL states as separate
full renderings:

S1 IDLE (first visit): title ("Get today's free config" / «کانفیگ رایگان امروزت را بگیر»),
   allowance chip showing dynamic daily volume (e.g. «حجم روزانهٔ شما: ۱ گیگابایت»), horizontal
   scrollable row of location chips (flag emoji + name, single-select, e.g. Germany 🇩🇪,
   Ukraine 🇺🇦, USA 🇺🇸, Turkey 🇹🇷), big primary CTA "Get config" / «دریافت کانفیگ», reassurance
   microcopy under CTA: no signup · free · renews every 24h (dynamic hours). A barely-visible
   anti-bot note ("protected by an invisible check"). NO login anywhere.
S2 PROVISIONING: CTA morphs to loading (spinner + "Preparing your config…"), chips disabled,
   subtle progress shimmer. Must feel < 3s.
S3 SUCCESS (Provisioned): celebratory but tasteful reveal — check morph on the CTA, then the
   config panel: location title, LTR monospace copy-field with the vless:// link + big copy
   button, QR toggle, "open in app" quick actions (v2rayNG, Hiddify, Streisand — icon buttons),
   remaining-time countdown (e.g. 23:59:12, tabular), usage meter 0 of 1 GB. Below: ONE
   dismissible missions strip: "Want more daily volume?" with dynamic reward chips
   (Invite a friend +N MB · Install web app +N MB · Turn on notifications +N MB) linking to the
   missions page. No account/login upsell of any kind.
S4 ACTIVE (returning user, config still valid): compact status header ("Your config is active"),
   countdown + usage meter (e.g. 380 MB of 1 GB), copy-field + QR + open-in-app again, secondary
   action "Change location" which re-opens the location chips inline (instant switch within the
   same trial — no new claim).
S5 COOLDOWN (trial ended, next claim locked): friendly lock state — "Next config in 07:12:44"
   (live countdown derived from the user's own last claim), plus the missions strip so the wait
   converts.
S6 DATA EXHAUSTED but time remains: distinct warm state — "Today's volume is used up" with the
   usage meter full, and the golden revive offer: "Invite ONE friend and this config comes back
   to life instantly" with an invite-link copy-field + native share button (Web Share API). Show
   the revived confirmation micro-state too.
S7 EMPTY (no locations / not configured): graceful maintenance state — illustration, "Locations
   are being refreshed, check back soon", link to the FAQ.
S8 ERROR (transient panel failure): calm error card — "Something hiccuped, your claim is
   untouched", a single Retry button (one retry only), link to FAQ/support. Never blame the user.

Also design the tiny inline anti-bot badge placement and a COMPACT widget variant (for SEO
landing pages: location pre-selected, shorter header). Deliver per the QUALITY BAR.
```

**چک‌لیست پذیرش:**
- [ ] هر ۸ حالت + واریانت فشردهٔ لندینگ طراحی شده و بین موبایل/دسکتاپ سالم‌اند.
- [ ] لینک کانفیگ در RTL هم کاملاً LTR، مونواسپیس و کپی‌پذیر است؛ QR و دکمه‌های «باز کردن در اپ» هست.
- [ ] هیچ عدد اقتصادی (حجم/ساعت/جایزه) هاردکد ننوشته شده — همه با لِیبل «داینامیک» مشخص‌اند.
- [ ] حالت revive (S6) واضح، جذاب و قابل‌فهم است — مهم‌ترین لحظهٔ رشد ویروسی محصول.
- [ ] شمارش‌گرها tabular و بدون پرش عرض‌اند؛ تایمر در fa با ارقام فارسی است.
- [ ] نوار ماموریت‌ها قابل‌بستن (dismiss) است و هیچ‌جا حس لاگین/ثبت‌نام وجود ندارد.

---

### فاز ۲ — صفحهٔ اصلی کامل + هدر و فوتر

**هدف:** صفحهٔ اصلی end-to-end با ویجت تأییدشده به‌عنوان هیرو.

**پرامپت:**

```text
PHASE 2 — FULL HOMEPAGE + GLOBAL HEADER/FOOTER

Using the CONTEXT + approved Phases 0–1, design the complete homepage (fa RTL default; also en):

HEADER (sticky, blur backdrop): logo "GozarX", nav (Get config, Locations, More volume, Guides,
FAQ, Blog), language switcher (فا/EN), theme toggle, and a "My status" ghost button. Mobile:
bottom-sheet menu. Active-page indicator.
1. HERO: the Phase-1 claim widget (S1) on a soft brand gradient (mirrored angle in RTL) with a
   short H1 above it targeting the head keyword ("Free daily V2Ray config" / «کانفیگ رایگان
   روزانه، در چند ثانیه») + one supporting line. Under the widget: trust chips (No signup ·
   Free forever · New config every 24h · ~N users — dynamic).
2. HOW IT WORKS: 3 steps (pick location → get config → import to app), direction-aware stepper.
3. LOCATIONS GRID: flag cards linking to location landing pages, each with a "get →" affordance;
   "all locations" link.
4. MORE VOLUME STRIP: 3–4 mission cards (Invite friends +N MB each up to a cap, Install web app
   +N MB, Enable notifications +N MB, Daily check-in) with a "see all missions" link — numbers
   rendered as dynamic tokens.
5. APPS ROW: v2rayNG / Hiddify / Streisand / Windows clients with platform icons → guides.
6. STATS BAND: configs delivered, active locations, uptime — animated count-up, tabular.
7. FAQ TEASER: top 5 questions, accordion.
8. PRIVACY/TRUST BAND: the "zero signup" promise — «بدون ثبت‌نام، بدون ایمیل، بدون شماره» with a
   one-line plain-language note on device-based identity and a link to the Privacy page.
9. BLOG TEASER: 3 article cards (title, read-time, tag).
FOOTER: 4 columns (product, resources, legal, language links fa/en) + small print. No social or
messenger links anywhere; support goes through the Contact page.
Also include: the language-suggestion banner (shown when browser locale ≠ page locale — never an
auto-redirect), scroll-triggered reveals (respect reduced motion). Deliver per the QUALITY BAR.
```

**چک‌لیست پذیرش:**
- [ ] هیرو بدون اسکرول در موبایل ۳۶۰px قابل‌استفاده است (ویجت بالای فولد).
- [ ] هدر sticky در RTL آینهٔ کامل LTR است؛ منوی موبایل bottom-sheet روان دارد.
- [ ] گرادیان‌ها و استپر در RTL جهتشان برعکس شده.
- [ ] بنر پیشنهاد زبان طراحی شده (بدون ریدایرکت خودکار).
- [ ] باند «بدون ثبت‌نام» شفاف و اعتمادساز است؛ هیچ لینک پیام‌رسان/شبکهٔ اجتماعی در صفحه نیست.
- [ ] چگالی محتوایی صفحه برای سئو کافی است ولی شلوغ نشده؛ سلسله‌مراتب H1→H2 منطقی است.

---

### فاز ۳ — صفحهٔ «حجم بیشتر» (ماموریت‌ها)

**هدف:** موتور رشد. کارت‌های ماموریت با حالت‌های کامل.

ماموریت‌های نهایی (همه با مقدار جایزهٔ داینامیک از تنظیمات پنل):

| ماموریت | جایزه (کلید تنظیمات برای فاز ساخت) | نوع |
|---|---|---|
| دعوت دوستان (به‌ازای هر نفر، تا سقف) | `site_referral_reward_mb` × سقف `site_referral_reward_limit` | تکرارشونده با سقف |
| نصب وب‌اپ (PWA) | `site_reward_pwa_mb` | یک‌باره |
| روشن‌کردن اعلان‌ها | `site_reward_push_mb` | یک‌باره |
| ورود روزانه (streak) | `site_reward_streak_mb` بعد از `site_streak_days` روز پیاپی | تکرارشونده |

**پرامپت:**

```text
PHASE 3 — "MORE VOLUME" MISSIONS PAGE (/rewards)

Using the CONTEXT + approved system, design the missions page:
- Page header: current daily allowance as a hero stat (ring gauge, e.g. «۱٫۵ گیگابایت در روز»)
  with a breakdown line (base + invites + missions — all dynamic).
- INVITE CARD (primary, larger): personal invite link in an LTR copy-field, a native share
  button (Web Share API sheet) + copy, progress "3 of 10 invites" with a segmented progress bar,
  "+N MB per friend" dynamic label, and the revive reminder ("an invite can instantly revive an
  exhausted config").
- MISSION CARDS grid, each with icon, title, dynamic reward chip (+N MB), state variants:
  available / in-progress / done-claimed (checkmark, muted) / unavailable-on-this-device (e.g.
  web app already installed, iOS notification limitations — with a gentle explainer tooltip):
  Install web app · Enable notifications · Daily check-in streak (7-day dots row,
  direction-aware).
- Claim interaction: mission completes → card flips to success with a "+N MB added to your daily
  volume" toast.
- Fine-print block: rules (per-device, anti-abuse note) in muted small text.
Both locales, both themes, mobile+desktop, per the QUALITY BAR.
```

**چک‌لیست پذیرش:**
- [ ] همهٔ جایزه‌ها لیبل داینامیک دارند؛ هیچ عددی هاردکد قطعی نشده.
- [ ] پیشرفت دعوت‌ها segmented و جهت‌آگاه است؛ سقف دعوت نمایش داده می‌شود.
- [ ] حالت‌های done / unavailable هر کارت طراحی شده.
- [ ] ردیف streak در RTL از راست شروع می‌شود.
- [ ] اشتراک‌گذاری با share بومی مرورگر است (بدون دکمهٔ اختصاصی هیچ پیام‌رسانی).

---

### فاز ۴ — قالب لندینگ‌های سئو (لوکیشن و کلیدواژه)

**هدف:** قالبی که با آن ده‌ها لندینگ (از پنل ادمین) ساخته می‌شود: «کانفیگ اوکراین»، «آیپی ثابت
آمریکا»، «کانفیگ رایگان v2ray» و…

**پرامپت:**

```text
PHASE 4 — SEO LANDING TEMPLATE (/location/{slug} and /l/{keyword}) + LOCATIONS INDEX

Using the CONTEXT + approved system, design:
A) LANDING TEMPLATE — demonstrate with TWO filled examples: fa «کانفیگ اوکراین» (/location/ukraine)
   and fa «آیپی ثابت آمریکا» (/l/usa-static-ip); include one en example too.
   Structure top→bottom:
   1. Breadcrumb (Home › Locations › Ukraine).
   2. H1 with the exact keyword + a one-line promise.
   3. The COMPACT claim widget (Phase-1 variant) with the location PRE-SELECTED — zero clicks
      between landing and claiming.
   4. Benefit trio for this location (latency, use-cases, IP type) as icon cards.
   5. "How to use it" — 3-step mini-guide with links to platform guides.
   6. SEO content block: 2–3 short headed paragraphs (H2/H3), designed for comfortable fa reading
      (max line length ~38rem, 1.8 line-height).
   7. Location-specific FAQ accordion (4 items) — will carry FAQPage schema.
   8. Related links: other locations chips + related keyword pages.
   9. Final CTA band repeating the claim button.
B) LOCATIONS INDEX (/locations): filterable grid of location cards (flag, name, "popular" badge,
   claim shortcut), plus a short intro paragraph for SEO.
Both locales, both themes, mobile+desktop, per the QUALITY BAR.
```

**چک‌لیست پذیرش:**
- [ ] از ورود تا دکمهٔ دریافت روی لندینگ: صفر کلیک اضافه (لوکیشن پیش‌انتخاب).
- [ ] بلوک محتوای سئو خوانایی فارسی عالی دارد (عرض سطر محدود، فاصلهٔ سطر ۱٫۸).
- [ ] breadcrumb و FAQ آمادهٔ اسکیما هستند؛ سلسله‌مراتب هدینگ تمیز است.
- [ ] قالب واقعاً «قالب» است — با عوض‌کردن متن/لوکیشن نمی‌شکند.

---

### فاز ۵ — راهنماها، FAQ، وبلاگ و صفحات تکمیلی

**پرامپت:**

```text
PHASE 5 — GUIDES, FAQ, BLOG, ABOUT/CONTACT, LEGAL

Using the CONTEXT + approved system, design:
1. GUIDES INDEX (/guides): platform cards (Android, iOS, Windows, macOS, Linux) with app logos
   (v2rayNG, Streisand, Hiddify, …) and difficulty/time chips.
2. GUIDE DETAIL (/guides/android as the example): sticky in-page TOC (direction-aware), numbered
   step cards with screenshot placeholders (16:9, labeled), copy-fields for the config link, a
   troubleshooting accordion, a "was this helpful?" feedback row, prev/next platform links.
   This page will carry HowTo schema — keep steps semantically clean.
3. FAQ PAGE (/faq): search input, category tabs (Getting started, Volume & invites, Apps,
   Troubleshooting), accordions; empty search-result state.
4. BLOG: index (featured post + card grid, tag filter) and post template (cover, meta row with
   Persian date + read-time, beautiful fa long-form typography, LTR code/link islands, an
   in-article CTA band with the compact claim widget, related posts).
5. ABOUT + CONTACT: short mission block; CONTACT is a lightweight form (topic select + message +
   optional reply handle — nothing required beyond the message), with success/error states, an
   expected-response-time note, and FAQ deflection links above the form. No email addresses, no
   social/messenger links.
6. TERMS + PRIVACY: clean legal template (numbered sections, sticky TOC); the privacy page
   explicitly explains the device-identity approach in plain language (what we store, what we
   never store — no name, no email, no phone).
Both locales, both themes, mobile+desktop, per the QUALITY BAR.
```

**چک‌لیست پذیرش:**
- [ ] TOC چسبان در RTL سمت درست است و اسکرول‌اسپای دارد.
- [ ] تایپوگرافی مقالهٔ فارسی (فاصله‌ها، نقل‌قول، لیست‌ها) بی‌نقص است؛ جزیره‌های LTR تمیزند.
- [ ] فرم تماس بدون هیچ فیلد اجباریِ هویتی است و حالت موفق/خطا دارد.
- [ ] صفحهٔ حریم خصوصی، هویت دستگاه را به زبان ساده و صادقانه توضیح می‌دهد.
- [ ] جستجوی FAQ حالت خالی دارد.

---

### فاز ۶ — «وضعیت من» + انتقال دستگاه

**هدف:** داشبورد سبک مبتنی بر دستگاه (بدون لاگین). تداوم بین‌دستگاهی با «کد انتقال» یک‌بارمصرف —
مکانیزم بدون‌حساب برای اینکه پاک‌شدن کوکی/تعویض گوشی، سوابق و دعوت‌های کاربر را نابود نکند.
(اگر این قابلیت را نخواستید، بند 2 پرامپت را حذف کنید.)

**پرامپت:**

```text
PHASE 6 — MY STATUS (/status) + DEVICE TRANSFER

Using the CONTEXT + approved system, design:
1. STATUS DASHBOARD (device-identity based, no login):
   - Top stat row: today's usage ring (e.g. 380 MB of 1 GB), time-remaining countdown, daily
     allowance, invites count (3 of 10) — all dynamic, tabular.
   - Active config card (reuses Phase-1 S4 essentials) or, if none, an inline claim CTA.
   - Claim history list (last N: date · location · status chip), empty state for new devices.
   - Missions summary strip linking to /rewards.
   - Settings block: language, theme, notifications toggle (permission-state aware).
   - A subtle identity note: "Your history lives on this browser" with a link to Device Transfer.
2. DEVICE TRANSFER (account-less cross-device continuity):
   - "Move to a new device" card → modal: generates a one-time 8-character code (LTR monospace
     copy-field) with a 10-minute expiry countdown; states: generated/waiting → redeemed-success
     → expired (regenerate).
   - On the NEW device (empty dashboard): "Used GozarX before? Enter your transfer code" entry
     point with a code input; success state (identity restored, stats animate in) and error
     states (wrong / expired code).
3. Danger row: "Reset this device's data" with a confirm dialog.
Both locales, both themes, mobile+desktop, per the QUALITY BAR.
```

**چک‌لیست پذیرش:**
- [ ] داشبورد بدون هیچ لاگینی معنا دارد؛ هیچ ردی از حساب/پیام‌رسان نیست.
- [ ] فلوی انتقال همهٔ حالت‌ها را دارد: در انتظار / موفق / منقضی / کد اشتباه.
- [ ] حالت خالی (دستگاه نو) و نقطهٔ ورود «قبلاً استفاده کرده‌ای؟» طراحی شده.
- [ ] کد انتقال LTR و مونواسپیس است؛ تایمر انقضا tabular.

---

### فاز ۷ — PWA، اعلان‌ها و صفحات سیستمی

**پرامپت:**

```text
PHASE 7 — PWA SURFACES + SYSTEM STATES

Using the CONTEXT + approved system, design:
1. PWA install: Android/desktop soft prompt (dismissible bottom-sheet: benefit line + dynamic
   +N MB reward chip + Install button), iOS Safari manual-steps modal (share icon → Add to Home
   Screen, illustrated), and the "installed" success state.
2. Push notifications: pre-permission explainer sheet (what we send: config-ready, volume-low,
   news — with the dynamic reward chip), then pointing to the native prompt; granted / denied /
   blocked-recovery states (how to unblock, per-browser hint).
3. Offline page (/offline): friendly, shows the last cached config (if any) in a copy-field,
   retry button.
4. 404: playful lost-connection illustration, search + top links. 500/maintenance: calm tone,
   a retry button and a link to the FAQ — no external status links.
5. Global loading skeletons (homepage hero + status page), toast stack position (define it
   direction-aware: top-start vs top-end — pick one and justify), and the app-update toast
   ("refresh for the new version").
Both locales, both themes, mobile+desktop, per the QUALITY BAR.
```

**چک‌لیست پذیرش:**
- [ ] پرامپت PWA قابل‌رد‌شدن است و آزاردهنده نیست؛ نسخهٔ iOS جدا طراحی شده.
- [ ] فلوی اعلان قبل از پرامپت مرورگر، توضیح می‌دهد (pre-permission) و حالت denied ریکاوری دارد.
- [ ] صفحهٔ آفلاین آخرین کانفیگ کش‌شده را نشان می‌دهد.
- [ ] جای toast در RTL/LTR تعریف و توجیه شده.

---

### فاز ۸ — ممیزی نهایی (دابل چک سراسری)

**پرامپت:**

```text
PHASE 8 — FINAL CROSS-CUTTING AUDIT

Take ALL approved phases and produce an audit report + corrected deliverables where needed:
1. RTL/LTR: walk every screen in both directions; list every asymmetry (icon flips, gradient
   angles, progress direction, toast position, chevron direction in accordions, stepper flow,
   scroll shadows). Fix and re-render offenders.
2. Spacing rhythm: verify every gap/padding is on the 4px grid and the section rhythm (96/64/48)
   is consistent across pages; flag inconsistencies in a table.
3. Contrast & a11y: AA check on every text/background token pair in both themes; focus order and
   focus-visible on all interactive elements; hit-targets ≥44px on mobile; reduced-motion
   variants exist.
4. Copy pass: fa copy natural (no translationese), Persian digits everywhere in fa except LTR
   technical islands; en copy idiomatic; terminology consistent (config / کانفیگ, volume / حجم,
   invite / دعوت — one term each, sitewide). Confirm ZERO login/signup/account/messenger wording
   anywhere.
5. Responsive matrix: 360 / 768 / 1280 for every page; no horizontal scroll anywhere.
6. State coverage: cross-check that the claim widget's 8 states + mission-card states + device-
   transfer states + PWA/notification states all exist in the final files.
Output: a pass/fail table per page per check, then corrected final HTML files.
```

**چک‌لیست پذیرش (تأیید نهایی UI):**
- [ ] جدول ممیزی، همهٔ صفحات را در هر ۶ محور pass نشان می‌دهد.
- [ ] خود شما دو صفحهٔ تصادفی را در حالت fa/dark/موبایل چک کرده‌اید و ایرادی ندیدید.
- [ ] بستهٔ نهایی توکن‌ها (CSS variables) یکجا استخراج شده — ورودی مستقیم فاز ساخت.

---

## ۵) استراتژی سئو (ورودی طراحی + فاز ساخت)

**خوشه‌های کلیدواژه (نمونه — لیست کامل در پنل ادمین مدیریت می‌شود):**

- هسته: کانفیگ رایگان، کانفیگ v2ray رایگان، کانفیگ vless رایگان، فیلترشکن رایگان روزانه،
  اکانت آزمایشی VPN.
- لوکیشن: کانفیگ اوکراین، کانفیگ آلمان، کانفیگ ترکیه، کانفیگ فرانسه، آیپی ثابت آمریکا،
  آیپی انگلیس.
- اپ/آموزش: آموزش v2rayNG، آموزش Hiddify، کانفیگ برای آیفون (Streisand)، اتصال در ویندوز.

**اصول فنی (در فاز ساخت اجرا می‌شود؛ طراحی باید جا بدهد):**

- SSG + ISR برای صفحهٔ اصلی/لندینگ‌ها/راهنماها؛ SSR فقط برای `‎/status‎`. ویجت claim به‌صورت
  جزیرهٔ کلاینتی روی صفحهٔ استاتیک.
- `hreflang` دوطرفهٔ `fa`/`en` + `x-default→fa`؛ canonical per-locale؛ بدون ریدایرکت IP.
- JSON-LD: `Organization` + `WebSite` (سراسری)، `FAQPage` (لندینگ‌ها/FAQ)، `HowTo` (راهنماها)،
  `BreadcrumbList`، `Article` (وبلاگ).
- `sitemap.xml` تفکیک‌شده per-locale، `robots.txt`، OG/Twitter card با تصویر قالب‌دار برای هر
  لندینگ (og-image با کلیدواژه).
- بودجهٔ پرفورمنس: LCP < 2.5s روی 3G سریع، INP < 200ms، CLS < 0.1؛ فونت‌ها self-host +
  `font-display: swap` + preload وزن 400/700؛ تصاویر AVIF/WebP با ابعاد صریح.
- عنوان/توضیح متا و H1 هر لندینگ از پنل ادمین قابل‌ویرایش (per-locale).

---

## ۶) یادداشت‌های فاز ساخت (خلاصه — اسپک کامل بک‌اند، سند بعدی)

این بخش فقط قرارداد کلی است تا طراحی با واقعیت ساخت نچسبد به هم؛ جزئیات در اسپک فاز ساخت.

- **سرویس جدید `site`** (Next.js standalone) در docker-compose، پشت همان nginx:
  `/` → site، `‎/admin‎` → SPA فعلی، `‎/api‎`، `‎/tg‎`، `‎/panel-webhook‎` مثل قبل → app.
- **API عمومی** زیر `‎/api/public/*‎` (جدا از `‎/api/admin‎`): `POST /claim`، `GET /status`،
  `GET /locations`، `POST /rewards/claim`، `POST /push/subscribe`، `POST /transfer/create`،
  `POST /transfer/redeem`، `POST /contact` — با rate-limit در Redis بر پایهٔ device+IP و
  راستی‌آزمایی Turnstile سمت سرور. منطق claim از **همان `TrialService`** استفاده می‌کند
  (لایه‌بندی موجود: delivery جدید → services موجود).
- **هویت دستگاه:** کوکی امضاشدهٔ httpOnly (UUID + HMAC) + هش fingerprint سبک + bucket آی‌پی.
  کد انتقال: یک‌بارمصرف، ۸ کاراکتری، انقضای ۱۰ دقیقه، ذخیره در Redis.
- **جدایی داده‌ای از بات:** کاربران سایت در جدول‌های خودشان — `site_devices`، `site_claims`،
  `site_rewards`، `push_subscriptions`، `site_messages` (فرم تماس) — و هیچ ردیفی در جدول
  `users` بات نمی‌سازند.
- **اقتصاد مستقل سایت (settings):** `site_trial_squad` (می‌تواند همان squad بات یا squad جدا
  باشد)، `site_trial_hours`، `site_daily_limit_mb`، `site_referral_reward_mb`،
  `site_referral_reward_limit`، `site_reward_pwa_mb`، `site_reward_push_mb`،
  `site_reward_streak_mb`، `site_streak_days`.
- **بخش جدید پنل ادمین «وب‌سایت»:** تنظیمات بالا، CRUD لندینگ‌های کلیدواژه‌ای (slug،
  عنوان/متا/محتوا per-locale)، آمار قیف سایت (بازدید→claim)، اینباکس فرم تماس، و مدیریت
  push broadcast (از همان arq worker).
- همهٔ قراردادهای CLAUDE.md پابرجاست: اعداد از settings، کپی از content (کلیدهای `site_*`)،
  بدون retry بی‌کران، لوکیشن با نام remark.

---

## ۷) دابل چک نهایی پروژهٔ UI (قبل از شروع فاز ساخت)

- [ ] هر ۹ فاز (۰–۸) تأیید شده و فایل‌های نهایی HTML یکجا آرشیو شده‌اند.
- [ ] بستهٔ توکن نهایی (CSS variables) و جدول آیکون‌های flip استخراج شده.
- [ ] لیست کامل کپی‌های دوزبانه (microcopy) از فایل‌ها بیرون کشیده و به‌عنوان کلیدهای `content`
  آماده شده (برای seed فاز ساخت).
- [ ] تصمیم‌های باز باقی‌مانده: هیچ. (اگر در طول فازها تصمیم تازه‌ای اضافه شد، همین‌جا ثبت شود.)
