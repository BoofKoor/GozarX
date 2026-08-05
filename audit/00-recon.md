# Phase 0 — شناسایی و harness رندر

**تاریخ:** ۲۰۲۶-۰۸-۰۵ · **وضعیت:** READ-ONLY، هیچ فایلی خارج از `audit/` لمس نشد
**هدف این فاز:** دیدن محصول واقعی در هر شرایطی که اهمیت دارد، و توافق بر سر مرز دامنه. **هیچ finding‌ای
در این گزارش نیست** — قضاوت از Phase 1 شروع می‌شود. اینجا فقط واقعیت ثبت می‌شود.

---

## ۰. سه فرضِ brief که با کدبیس نمی‌خواند

این مهم‌ترین خروجی Phase 0 است، چون دامنهٔ سه فاز بعد را تغییر می‌دهد.

| فرض brief | واقعیت | شاهد |
|---|---|---|
| Telegram Mini App با `Telegram.WebApp` / `initData` / `themeParams` | **وجود ندارد.** صفر ارجاع در کل `frontend/site`. تنها اثر تلگرام یک کامنت است دربارهٔ محدودیت clipboard در WebView اندروید. | `grep -rn "Telegram\|initData\|tgWebApp"` روی کل site → یک نتیجه: `lib/clipboard.ts:2` |
| سه locale: `fa` / `en` / `ru` | **فقط `fa` و `en`.** روسی در کد نیست. | `lib/i18n.ts:6` — `export const LOCALES = ["fa", "en"] as const;` |
| Tailwind config برای استخراج design tokens | **Tailwind نصب نیست.** استایل CSS خام است. | `package.json` (۳ dependency: next, react, react-dom) · `app/globals.css` |

**تصمیم مالک:** تلگرام کاملاً از دامنه حذف شد. بنابراین «مسیر ورود کاربر گرم از تلگرام» که در brief
محور بود، در فازهای ۱ تا ۴ ارزیابی نمی‌شود. یک شات مرجع با User-Agent واقعیِ WebView تلگرام گرفته شده
(`fa-360-home-tg-webview-dark-first.png`) صرفاً برای ثبت، نه برای ممیزی.

**پیامد برای Phase 2:** بند «arbitrary Tailwind values» بی‌موضوع است. معادلش برای این کدبیس، نسبت
custom property به مقدار یک‌بارمصرف است که در بخش ۶ اندازه‌گیری شده.

یک نکتهٔ ساختاری دیگر که brief فرض نکرده بود: **هیچ segment `[locale]` در مسیرها نیست.** زبان از
cookie → `Accept-Language` → `fa` حل می‌شود (`app/layout.tsx:22`, `lib/server.ts:7-12`)، یعنی یک URL
هر دو زبان را سرو می‌کند. این برای Phase 3 (SEO / `hreflang`) موضوع دارد.

---

## ۱. مرز دامنه — برای تأیید شما

**داخل دامنه:** `frontend/site/` — Next.js 16.2.10 (Turbopack) · React 19.2.0 · App Router ·
TypeScript strict · CSS خام · بدون کتابخانهٔ UI.

**خارج از دامنه:**

| مسیر | چیست | چرا مستثنا |
|---|---|---|
| `frontend/admin/` | پنل ادمین: Vite + React + Tailwind | صراحت brief |
| `backend/` | FastAPI + aiogram + arq | فقط تا جایی که علامت فرانت‌اندی بسازد |
| `docker/`, `nginx/`, `install.sh` | استقرار | خارج از دامنه |
| هر سطح تلگرام | — | دستور مالک (بخش ۰) |
| locale روسی | — | در کد وجود ندارد |

**ابهامی که می‌خواهم شما تعیین تکلیف کنید:** `docs/website/` شامل `UI_SPEC.md` و `REBUILD_SPEC.md` و
پوشهٔ `design/` است. اگر اینها همان artifact مرجعی هستند که سایت باید با آن سنجیده شود، Phase 2
می‌تواند عددی اندازه‌گیری کند (مثل کاری که برای پنل در فاز ۱۵–۱۶ شد). اگر منسوخ‌اند، بگویید تا نادیده
بگیرم و صرفاً بر اساس اصول قضاوت کنم.

---

## ۲. جدول route

هر ۱۸ صفحهٔ قابل دسترس. ستون «رندر» عیناً از خروجی build.

| route | هدف | فایل ورودی | رندر | داده از بک‌اند |
|---|---|---|---|---|
| `/` | لندینگ + ویجت دریافت کانفیگ | `app/page.tsx` | ƒ Dynamic | server: `site-copy`, `pages` · client: `status`, `config`, `locations`, `stats` |
| `/status` | حساب کاربری (حجم، دعوت، تاریخچه) | `app/status/page.tsx` | ƒ Dynamic | client: `status`, `config` |
| `/locations` | فهرست لوکیشن‌ها | `app/locations/page.tsx` | ƒ Dynamic | server: `pages` · client: `locations` |
| `/guides` | فهرست راهنماها | `app/guides/page.tsx` | ƒ Dynamic | — |
| `/guides/android` | **لحظهٔ hand-off** | `app/guides/[platform]/page.tsx` | ƒ Dynamic | — |
| `/guides/ios` | همان | همان | ƒ Dynamic | — |
| `/guides/windows` | همان | همان | ƒ Dynamic | — |
| `/guides/macos` | همان | همان | ƒ Dynamic | — |
| `/guides/linux` | همان | همان | ƒ Dynamic | — |
| `/faq` | سوالات متداول | `app/faq/page.tsx` | ƒ Dynamic | server: `faq` |
| `/about` | دربارهٔ ما | `app/about/page.tsx` | ƒ Dynamic | — |
| `/contact` | فرم تماس | `app/contact/page.tsx` | ƒ Dynamic | client: `contact` (POST) |
| `/privacy` | حریم خصوصی | `app/privacy/page.tsx` | ƒ Dynamic | — |
| `/terms` | قوانین | `app/terms/page.tsx` | ƒ Dynamic | — |
| `/l/[slug]` | لندینگ سئو (مقاله/لوکیشن) | `app/l/[slug]/page.tsx` | ƒ Dynamic | server: `pages/{slug}`, `pages` |
| `/offline` | صفحهٔ آفلاین PWA | `app/offline/page.tsx` | ƒ Dynamic | — |
| `/_not-found` | ۴۰۴ | `app/not-found.tsx` | ƒ Dynamic | — |
| `/icon.svg`, `/apple-icon.png`, `/robots.txt`, `/sitemap.xml` | asset | file convention | ○ Static | `sitemap` → `pages` |

**واقعیت قابل ثبت:** جز چهار asset، **هیچ صفحه‌ای static نیست** — همه `ƒ` (server-rendered on demand).
`app/layout.tsx:22-27` در ریشه `cookies()` و `getLocale()` (که `headers()` می‌خواند) را صدا می‌زند، و این
دو، dynamic API هستند. تحلیل هزینه‌اش کار Phase 3 است؛ اینجا فقط ثبت می‌شود.

**مرز RSC/client:** هر ۱۲ فایل `page.tsx` و `layout.tsx` سرور کامپوننت‌اند. `"use client"` در ۲۱ فایل
از ۲۶ کامپوننت است. عدد خام برای Phase 3.

**عنوان صفحه:** `/status` و `/offline` عنوان اختصاصی ندارند و همان عنوان صفحهٔ اصلی را به ارث می‌برند
(«کانفیگ رایگان V2Ray روزانه، بدون ثبت‌نام | گذرایکس GozarX»). `/status` در robots هم `Disallow` است.

---

## ۳. Build — خروجی عیناً

`npm ci` سپس `npm run build`، بدون بک‌اند (همان شرایطی که Docker build دارد؛ `lib/landing.ts:7`).

```
▲ Next.js 16.2.10 (Turbopack)

  Creating an optimized production build ...
✓ Compiled successfully in 6.1s
  Running TypeScript ...
  Finished TypeScript in 5.4s ...
  Collecting page data using 3 workers ...
✓ Generating static pages using 3 workers (16/16) in 314ms
  Finalizing page optimization ...

Route (app)             Revalidate  Expire
┌ ƒ /
├ ƒ /_not-found
├ ƒ /about
├ ○ /apple-icon.png
├ ƒ /contact
├ ƒ /faq
├ ƒ /guides
├ ƒ /guides/[platform]
├ ○ /icon.svg
├ ƒ /l/[slug]
├ ƒ /locations
├ ƒ /offline
├ ƒ /privacy
├ ○ /robots.txt
├ ○ /sitemap.xml                5m      1y
├ ƒ /status
└ ƒ /terms

○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand
```

**صفر warning.** `npm run typecheck` (`tsc --noEmit`) هم بدون خروجی و با exit code صفر تمام شد.

**نکتهٔ ابزاری:** Next 16 با Turbopack دیگر ستون **First Load JS** را چاپ نمی‌کند — جدول فقط
Revalidate/Expire دارد. `app-build-manifest.json` هم تولید نمی‌شود، پس حساب کردن از روی manifest ممکن
نبود. به‌جایش وزن واقعی هر route از روی سیم اندازه‌گیری شد (بخش ۵).

**`npm audit` عیناً:** «3 high severity vulnerabilities» — `next` (۹ advisory)، `postcss` (۴)، `sharp`
(۱). رفعشان `next@16.3.0` می‌خواهد که خارج از بازهٔ اعلام‌شدهٔ dependency است. بدون قضاوت ثبت می‌شود؛
تحلیل با Phase 3.

---

## ۴. Harness

سه فایل، همه داخل `audit/.harness/`، با `package.json` مستقل. هیچ چیزی به dependency tree پروژه اضافه
نشد.

**`mockapi.py`** — mock بک‌اند عمومی، با کتابخانهٔ استاندارد پایتون. Docker در این کانتینر در دسترس
نیست، پس بالا آوردن FastAPI + Postgres + Redis عملی نبود. shape هر پاسخ از **منبع** رونویسی شده، نه از
حافظه: تایپ‌های `frontend/site/lib/api.ts` و مدل‌های Pydantic در `backend/gozar/web/routes/public/*.py`.
اپ از طریق `BACKEND_ORIGIN` به آن وصل می‌شود — متغیری که `next.config.ts:6` از قبل پشتیبانی می‌کند، پس
**هیچ تغییری در کد پروژه لازم نشد.**

state با `POST /__state` عوض می‌شود. یازده state، منطبق بر همان S1..S8 که خود ویجت در
`components/ClaimWidget.tsx` کامنت کرده:

| state | چه چیزی را احضار می‌کند | تأیید شد |
|---|---|---|
| `first` | S1 — picker خالی، بازدید اول | `status=200 locs=12` |
| `claim_ok` | S3 — دریافت موفق (جشن) | `claim=200 ok:true` |
| `delivered` | S4 — بازگشتی، کانفیگ در دست | `status=200` |
| `exhausted` | S6 — حجم روزانه تمام | `status=200` |
| `cooldown` | S5 — امروز گرفته، بعدی ساعت‌ها بعد | `claim=200 reason:cooldown` |
| `no_locations` | S7 — squad هیچ لوکیشنی نمی‌دهد | `locs=0` |
| `panel_error` | S8 — خودِ `/status` می‌افتد | `status=502` |
| `rate_limited` | گارد امنیتی ۴۲۹ | `claim=429` |
| `location_unavailable` | لوکیشن بین رندر و claim حذف شد | `claim=200 + locations[]` |
| `turnstile` | CTA پشت اسکریپت Cloudflare | `turnstile_enabled:true` |
| `slow` | تأخیر ۳ ثانیه روی همهٔ APIها | skeleton |

**`capture.mjs`** — Playwright روی Chromium از پیش‌نصب‌شده. نسخهٔ playwright نصب‌شده revision 1234 را
می‌خواست ولی محیط 1194 دارد؛ طبق قاعدهٔ محیط مرورگر دانلود **نشد** و مستقیم به
`/opt/pw-browsers/chromium-1194/chrome-linux/chrome` وصل شد.

دو تصمیم که بر صحت شات‌ها اثر دارد:
- قبل از هر شات، صفحه تا انتها اسکرول و به بالا برگردانده می‌شود تا `RevealObserver` برای همهٔ
  سکشن‌ها fire کند. بدون این، شات full-page سکشن‌های `opacity:0` را ثبت می‌کرد و ممیزی داشت
  artifact خودِ harness را به‌عنوان نقص طراحی می‌خواند.
- `document.fonts.ready` انتظار کشیده می‌شود تا FOIT در شات ثبت نشود.

**`mock.log` / `next.log`** — لاگ خام دو سرویس.

---

## ۵. وزن واقعی هر route

`content-length` روی حدود نیمی از پاسخ‌ها وجود ندارد (Next پاسخ را chunked می‌فرستد)، پس اندازه‌گیری از
`Network.loadingFinished.encodedDataLength` در CDP گرفته شد — یعنی بایتی که واقعاً از سیم رد شد. بارگذاری
سرد، ۳۶۰px، تم دارک، locale فارسی.

| route | requests | JS kB | CSS kB | font kB | image kB | **total kB** |
|---|---:|---:|---:|---:|---:|---:|
| `/` | ۳۶ | ۱۸۳٫۷ | ۱۷٫۲ | ۶۲٫۵ | ۱۱۶٫۴ | **۳۹۸٫۰** |
| `/status` | ۳۰ | ۱۸۶٫۸ | ۱۷٫۲ | ۶۲٫۵ | ۸٫۷ | **۲۸۸٫۴** |
| `/l/what-is-vless` | ۳۰ | ۱۸۱٫۱ | ۱۷٫۲ | ۶۲٫۵ | ۸٫۷ | **۲۸۵٫۸** |
| `/l/free-v2ray-config-germany` | ۳۰ | ۱۸۱٫۱ | ۱۷٫۲ | ۶۲٫۵ | ۸٫۷ | **۲۸۳٫۳** |
| `/guides/linux` | ۱۷ | ۱۷۲٫۵ | ۱۷٫۲ | ۶۲٫۵ | ۳٫۹ | **۲۷۸٫۵** |
| `/locations` | ۲۸ | ۱۷۶٫۹ | ۱۷٫۲ | ۶۲٫۵ | ۸٫۷ | **۲۷۸٫۳** |
| `/guides` | ۱۶ | ۱۷۲٫۵ | ۱۷٫۲ | ۶۲٫۵ | ۳٫۹ | **۲۷۸٫۱** |
| `/guides/ios` | ۱۸ | ۱۷۲٫۵ | ۱۷٫۲ | ۶۲٫۵ | ۳٫۹ | **۲۷۴٫۰** |
| `/guides/macos` | ۱۸ | ۱۷۲٫۵ | ۱۷٫۲ | ۶۲٫۵ | ۳٫۹ | **۲۷۳٫۹** |
| `/guides/android` | ۱۶ | ۱۷۲٫۵ | ۱۷٫۲ | ۶۲٫۵ | ۳٫۹ | **۲۷۱٫۹** |
| `/guides/windows` | ۱۷ | ۱۷۲٫۵ | ۱۷٫۲ | ۶۲٫۵ | ۳٫۹ | **۲۷۰٫۸** |
| `/contact` | ۱۷ | ۱۷۴٫۷ | ۱۷٫۲ | ۶۲٫۵ | ۰ | **۲۶۸٫۴** |
| `/terms` | ۱۹ | ۱۷۲٫۵ | ۱۷٫۲ | ۶۲٫۵ | ۰ | **۲۶۸٫۳** |
| `/faq` | ۱۸ | ۱۷۴٫۱ | ۱۷٫۲ | ۶۲٫۵ | ۰ | **۲۶۷٫۴** |
| `/privacy` | ۱۶ | ۱۷۲٫۵ | ۱۷٫۲ | ۶۲٫۵ | ۰ | **۲۶۵٫۸** |
| `/_not-found` | ۱۷ | ۱۷۲٫۵ | ۱۷٫۲ | ۶۲٫۵ | ۰ | **۲۶۵٫۱** |
| `/offline` | ۱۶ | ۱۷۳٫۱ | ۱۷٫۲ | ۶۲٫۵ | ۰ | **۲۶۴٫۷** |
| `/about` | ۱۵ | ۱۷۲٫۵ | ۱۷٫۲ | ۶۲٫۵ | ۰ | **۲۶۴٫۳** |

منبع: `audit/diagnostics.json` (کلید `weight` هر رکورد).

سه واقعیت که بدون تفسیر ثبت می‌شوند: JS در بازهٔ **۱۷۲٫۵ تا ۱۸۶٫۸ کیلوبایت** روی *همهٔ* routeهاست
(اختلاف کل ۱۴ کیلوبایت، یعنی تقریباً همه‌چیز در bundle مشترک است) · صفحهٔ `/about` که فقط متن است
همان ۱۷۲٫۵ کیلوبایت JS را می‌گیرد · صفحهٔ اصلی با ۱۱۶ کیلوبایت تصویر (`map-world.webp` + آیکون اپ‌ها،
هر چهار تا در هدر `Link: rel=preload`) به ۳۹۸ کیلوبایت می‌رسد.

**Prefetch.** در لاگ، هر بارگذاری ده‌ها درخواست `?_rsc=…` به routeهای لینک‌شده می‌زند (prefetch پیش‌فرض
Next). این‌ها در `diagnostics.json` به‌صورت `requestfailed` دیده می‌شوند **چون harness بلافاصله پس از
شات context را می‌بندد و prefetchهای در پرواز لغو می‌شوند** — این artifact خود harness است، نه نقص
محصول. اما حجمِ خودِ prefetch واقعی است و برای Phase 3 ثبت می‌شود.

---

## ۶. اعداد خام برای فازهای بعد

بدون تفسیر — تفسیر کار Phase 2 و ۳ است.

| سنجه | مقدار | منبع |
|---|---|---|
| خطوط `app/globals.css` | ۱۳۷۲ | `wc -l` |
| custom property یکتای تعریف‌شده | ۵۶ | parse با regex روی `--x:` |
| custom property یکتای مصرف‌شده در `var()` | ۵۷ | parse |
| کل فراخوانی `var(--…)` | ۹۶۳ | `grep -c` |
| تعریف‌شده و هرگز مصرف‌نشده | ۳ (`--logo-accent`, `--logo-ink`, `--primary-2`) | parse |
| مصرف‌شده و در CSS تعریف‌نشده | ۴ (`--acc`, `--accent`, `--skel-1`, `--skel-2`) | parse — `--acc` در `app/guides/page.tsx:44` inline ست می‌شود |
| کل مقدار hex در CSS | ۱۵۳ | `grep -o` |
| از آن، داخل بلوک‌های توکن (`:root` / `[data-theme]`) | ۱۲۸ | parse |
| **hex یک‌بارمصرف بیرون از بلوک توکن** | **۲۵** | parse |
| `style={{…}}` inline در TSX | ۵۸ | `grep -c` |
| فایل با `"use client"` | ۲۱ از ۲۶ کامپوننت | `grep -rl` |

**منابع third-party.** تنها اسکریپت خارجی که در runtime بارگذاری می‌شود `challenges.cloudflare.com`
(Turnstile) است — `components/Turnstile.tsx:23`. **بدون Google Fonts، بدون Google Analytics، بدون CDN
خارجی.** فونت‌ها self-host هستند (`public/fonts/YekanBakh-VF.woff2` برای fa،
`Inter-Variable-latin.woff2` برای en). دامنه‌های دیگری که در کد هستند صرفاً **لینک مقصد**‌اند نه بارگذاری:
`play.google.com`، `apps.apple.com`، `github.com` (دانلود اپ Happ در صفحات راهنما).

**هدرهای پاسخ روی `/` (عیناً):**
```
Vary: rsc, next-router-state-tree, next-router-prefetch, next-router-segment-prefetch, Accept-Encoding
Cache-Control: private, no-cache, no-store, max-age=0, must-revalidate
X-Powered-By: Next.js
```
`Vary` شامل `Cookie` یا `Accept-Language` نیست، در حالی که زبان از همان‌ها حل می‌شود. `nginx/nginx.conf`
موجود در ریپو **هیچ** هدر امنیتی (CSP, HSTS, X-Frame-Options) اضافه نمی‌کند. `[UNVERIFIED]` برای
production: طبق `CLAUDE.md` فایل واقعی `nginx/nginx.tls.conf` فقط روی سرور است و git-ignored — برای
قطعیت باید هدرهای `https://gozarx.gozarxservices.com` از بیرون گرفته شود.

**SEO artifact:** `robots.txt` سالم است (`Disallow: /api/, /status, /offline`) و `sitemap.xml` همهٔ
route‌ها را دارد. **هیچ تگ `hreflang` در خروجی نیست** — که با یک URL برای دو زبان قابل بیان هم نیست.
`canonical` روی هر صفحه هست.

---

## ۷. ماتریس capture

**۱۰۵ شات** در `audit/screens/`، به‌علاوهٔ `audit/diagnostics.json` با ۱۰۶ رکورد (route، خطاهای
console، وزن، و هر شکستی که رخ داد).

| لایه | پوشش | تعداد |
|---|---|---:|
| A | هر ۱۸ route · fa · ۳۶۰×۶۴۰ · light + dark | ۳۶ |
| B | ۸ صفحهٔ کلیدی · en · ۳۶۰×۶۴۰ · light + dark | ۱۶ |
| C | ۵ صفحه‌ای که layout عوض می‌کنند · ۳۹۰ / ۴۱۲ / ۷۶۸ / ۱۴۴۰ · fa · dark | ۲۰ |
| D | ۱۱ state ویجت روی `/` و `/status` · fa · ۳۶۰ · dark | ۲۲ |
| E | شبکهٔ کند (~۴۰۰kbps / ۴۰۰ms) و offline روی `/`، `/status`، `/locations` | ۶ |
| F | close-up هدفمند: کیبورد باز روی `/contact`، کارت کانفیگ (bidi) در fa و en، دسکتاپ در fa و en، UA وب‌ویو تلگرام | ۷ |

| تفکیک | مقدار |
|---|---|
| locale | fa ۸۷ · en ۱۸ |
| عرض | ۳۶۰px ۸۳ · ۳۹۰px ۵ · ۴۱۲px ۵ · ۷۶۸px ۵ · ۱۴۴۰px ۷ |
| تم | dark ۷۹ · light ۲۶ |
| حجم | ۶۹ مگابایت |

**خطاهای console.** پس از کنار گذاشتن دو دستهٔ artifact (لغو prefetch هنگام بستن context، و
`ERR_INTERNET_DISCONNECTED` در شات‌های عمداً آفلاین)، تنها خطاهای باقی‌مانده دقیقاً همان state‌های
عمدی‌اند: ۵۰۲ ×۴ (`panel_error`)، ۴۲۹ ×۲ (`rate_limited`)، ۴۰۴ ×۲ (صفحهٔ ۴۰۴)، و
`ERR_TUNNEL_CONNECTION_FAILED` ×۲ (تلاش Turnstile برای رسیدن به `challenges.cloudflare.com` از این
کانتینر). یعنی: **صفر خطای غیرمنتظره، صفر warning، صفر hydration mismatch، صفر pageerror** در کل
۱۰۵ بارگذاری.

**دو نکتهٔ صداقتی دربارهٔ خودِ harness:**

1. شات‌های `panel_error` با `TimeoutError: page.goto` ثبت شده‌اند: با بک‌اندِ افتاده، `networkidle`
   هرگز fire نشد. شات با این حال گرفته شد و **کاملاً معتبر است** (کارت خطای S8 با «تلاش دوباره» به‌جای
   ویجت دیده می‌شود). علت اینکه شبکه idle نشد تعیین نشد؛ در `lib/useSite.ts` هیچ حلقهٔ polling و در
   `public/sw.js` هیچ interval‌ای نیست، پس به احتمال زیاد artifact استراتژی انتظارِ harness است نه
   رفتار محصول — `[UNVERIFIED]`، برای تأیید در Phase 3.
2. در اجرای اول، شات‌های offline و throttled به‌خاطر نام‌گذاری من با شات‌های عادیِ همان route هم‌نام
   شدند و رویشان نوشتند. با افزودن `tag` به نام فایل رفع شد و همان زیرمجموعه دوباره گرفته شد
   (`recapture-e.mjs`). فایل‌های `*-first-offline.png` و `*-slow-slow3g.png` نتیجهٔ اجرای دوم‌اند.
3. سرور mock چهارده `BrokenPipeError` لاگ کرد. هر چهارده مورد یعنی کلاینت وسط پاسخ رفت — بستن
   context پس از شات، و شات‌های عمداً آفلاین. هیچ‌کدام پاسخ نادرست نبود، پس اعتبار هیچ شاتی را
   خدشه‌دار نمی‌کند. لاگ‌های runtime (`mock.log`, `next.log`) commit نشده‌اند.

نام‌گذاری: `<locale>-<width>-<route>-<theme>-<state>.png`. همه full-page، DPR ۲.

---

## ۸. blockerها و چیزهایی که قابل دسترسی نبود

| مورد | وضعیت | برای رفع چه لازم است |
|---|---|---|
| بک‌اند واقعی | Docker در کانتینر در دسترس نیست | با mock پوشش داده شد. اگر می‌خواهید اعداد واقعی (تعداد کانفیگ تحویل‌شده، uptime، لوکیشن‌های واقعی) دیده شود، یک پاس روی `gozarx.gozarxservices.com` لازم است — که رکورد device واقعی می‌سازد و یک claim روزانه مصرف می‌کند. |
| اسکریپت Turnstile | از این کانتینر بارگذاری نمی‌شود | state `turnstile` رفتار *وقتی CTA پشت Turnstile قفل است* را نشان می‌دهد. رفتار واقعی «Turnstile در ایران بارگذاری نمی‌شود» فقط از یک شبکهٔ ایرانی قابل تأیید است — `[UNVERIFIED]`، Phase 3. |
| هدرهای امنیتی production | `nginx.tls.conf` در ریپو نیست | یک `curl -I https://gozarx.gozarxservices.com` از سمت شما. |
| Lighthouse / axe | در این فاز اجرا نشد | طبق brief متعلق به Phase 3 است. |
| Web Push | نیازمند مجوز مرورگر + VAPID واقعی | mock کلید برمی‌گرداند ولی subscribe واقعی رخ نمی‌دهد. |

---

## ۹. گیت

Phase 1 شروع نمی‌شود تا شما این گزارش و مرز دامنهٔ بخش ۱ را تأیید کنید.
