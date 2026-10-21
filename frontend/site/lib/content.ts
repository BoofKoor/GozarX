// Static content-page copy (legal / faq / guides), bilingual, in-code. /about moved to the
// design copy, where the panel can override its prose (site copy, "about" group).
// Per CLAUDE.md the site keeps chrome + static copy in code (the DB `content` table holds bot copy
// and, later, admin-managed keyword landings — not these evergreen pages). Copy is extracted from
// the approved Phase-5 design mockup (docs/website/design/phase-5-content.html); the iOS/Windows/
// macOS/Linux guide steps are authored to match the Android/v2rayNG guide's shape (the mockup only
// detailed Android). Keep both `fa` and `en` in sync.

import type { Locale } from "@/lib/i18n";

// ── Legal (privacy / terms share one section shape) ───────────────────────────
export interface LegalSection {
  h: string;
  body: string;
  important?: boolean; // rendered as an emphasised "Important:" callout
}

// The day the legal TEXT last changed — one ISO date, printed per locale by `legalUpdated`. It
// replaces two hand-written strings («تیر ۱۴۰۴» / "July 2025") that were the design mockup's
// placeholder, not a date anything happened on. Change it in the same commit as the text.
export const LEGAL_UPDATED_AT = "2026-09-30";

export function legalUpdated(locale: Locale): string {
  const when = new Date(`${LEGAL_UPDATED_AT}T12:00:00Z`);
  const fmt = new Intl.DateTimeFormat(locale === "fa" ? "fa-IR-u-ca-persian" : "en-US", {
    year: "numeric",
    month: "long",
    timeZone: "Asia/Tehran",
  });
  // Month first in both: ICU's Persian month-year pattern is «۱۴۰۵ مهر», and the order people
  // write is «مهر ۱۴۰۵».
  const part = (type: string) => fmt.formatToParts(when).find((p) => p.type === type)?.value ?? "";
  const date = `${part("month")} ${part("year")}`;
  return locale === "fa" ? `آخرین به‌روزرسانی: ${date}` : `Last updated: ${date}`;
}

export const LEGAL_TOC: Record<Locale, string> = { fa: "در این صفحه", en: "On this page" };

export const LEGAL_TITLE: Record<Locale, { privacy: string; terms: string }> = {
  fa: { privacy: "حریم خصوصی", terms: "قوانین استفاده" },
  en: { privacy: "Privacy", terms: "Terms of use" },
};

export const LEGAL_IMPORTANT: Record<Locale, string> = { fa: "مهم:", en: "Important:" };

export const PRIVACY: Record<Locale, LegalSection[]> = {
  fa: [
    { h: "اطلاعاتی که ذخیره نمی‌کنیم", body: "برای دریافت کانفیگ هیچ نام، ایمیل یا شماره‌ای نمی‌گیریم و ذخیره نمی‌کنیم." },
    {
      h: "هویت دستگاه چطور کار می‌کند؟",
      body: "هویت تو فقط با یک «شناسهٔ سبک روی همین مرورگر» ساخته می‌شود: یک کوکی امضاشده. کنارش یک اثر انگشت سادهٔ مرورگر و یک هش نمک‌دار از محدودهٔ شبکه‌ات (نه خود IP) هم نگه داشته می‌شود. شناسه برای این است که حجم روزانه و دعوت‌هایت را روی همین دستگاه به‌خاطر بسپاریم و آن دو نشانه فقط برای جلوگیری از سوءاستفاده‌اند — هیچ‌کدام برای شناسایی شخص تو نیست.",
      important: true,
    },
    { h: "کوکی‌ها", body: "فقط از کوکی‌های ضروری برای کارکرد سرویس استفاده می‌کنیم؛ کوکی تبلیغاتی یا ردگیری شخص ثالث نداریم." },
    { h: "اشتراک‌گذاری", body: "اطلاعات تو را به شخص ثالث نمی‌فروشیم و به اشتراک نمی‌گذاریم." },
    { h: "پاک‌کردن داده", body: "با پاک‌کردن کوکی/دادهٔ مرورگر، شناسهٔ دستگاهت پاک می‌شود و از نو شروع می‌کنی." },
  ],
  en: [
    { h: "What we don't store", body: "To claim a config we take and store no name, email or phone number." },
    {
      h: "How device identity works",
      body: "Your identity is just a “light token kept on this browser”: a signed cookie. Beside it we keep a simple browser fingerprint and a salted hash of your network range (not the IP itself). The token lets us remember your daily volume and invites on this device, and the two signals exist only to prevent abuse — none of it identifies you personally.",
      important: true,
    },
    { h: "Cookies", body: "We only use cookies essential to the service; no advertising or third-party tracking cookies." },
    { h: "Sharing", body: "We do not sell or share your information with third parties." },
    { h: "Clearing data", body: "Clearing your browser cookies/data removes your device identity and you start fresh." },
  ],
};

export const TERMS: Record<Locale, LegalSection[]> = {
  fa: [
    { h: "پذیرش قوانین", body: "با استفاده از GozarX، این قوانین را می‌پذیری. اگر با آن‌ها موافق نیستی، از سرویس استفاده نکن." },
    { h: "ماهیت سرویس", body: "GozarX یک ابزار رایگان است که کانفیگ آزمایشی روزانه می‌دهد. سرویس «همان‌طور که هست» ارائه می‌شود و تضمینی برای در دسترس بودن دائمی نیست." },
    { h: "استفادهٔ منصفانه", body: "استفاده از چند حساب، ربات یا هر روش سوءاستفاده برای گرفتن حجم بیشتر ممنوع است و باعث لغو دسترسی می‌شود." },
    { h: "مسئولیت کاربر", body: "مسئولیت استفاده از کانفیگ‌ها بر عهدهٔ خودت است؛ برای فعالیت‌های غیرقانونی از سرویس استفاده نکن." },
    { h: "تغییرات", body: "ممکن است این قوانین به‌مرور به‌روزرسانی شوند. نسخهٔ جدید از همین صفحه در دسترس خواهد بود." },
  ],
  en: [
    { h: "Accepting the terms", body: "By using GozarX you accept these terms. If you don't agree with them, please don't use the service." },
    { h: "Nature of the service", body: "GozarX is a free tool that provides a daily trial config. The service is provided “as is” with no guarantee of permanent availability." },
    { h: "Fair use", body: "Using multiple accounts, bots or any abusive method to gain more volume is prohibited and will void your access." },
    { h: "User responsibility", body: "You are responsible for how you use the configs; do not use the service for illegal activity." },
    { h: "Changes", body: "These terms may be updated over time. The latest version will be available on this page." },
  ],
};

// ── FAQ ───────────────────────────────────────────────────────────────────────
export interface FaqCategory {
  id: string;
  label: string;
}
export interface FaqItem {
  cat: string;
  q: string;
  a: string;
}

export const FAQ_LABELS: Record<
  Locale,
  { title: string; sub: string; search: string; empty: string; ask: string; all: string; categories: string }
> = {
  fa: {
    title: "سوالات متداول",
    sub: "پاسخ سریع به پرتکرارترین سوال‌ها. اگر جوابت این‌جا نبود، از صفحهٔ تماس بپرس.",
    search: "جستجو در سوالات…",
    empty: "سوالی با این عبارت پیدا نشد.",
    ask: "سوالت را از ما بپرس",
    all: "همه",
    categories: "دسته‌ها",
  },
  en: {
    title: "Frequently asked questions",
    sub: "Quick answers to the most common questions. If yours isn't here, ask on the contact page.",
    search: "Search questions…",
    empty: "No question matches that phrase.",
    ask: "Ask us your question",
    all: "All",
    categories: "Categories",
  },
};

export const FAQ_CATS: Record<Locale, FaqCategory[]> = {
  fa: [
    { id: "start", label: "شروع" },
    { id: "vol", label: "حجم و دعوت" },
    { id: "apps", label: "اپ‌ها" },
    { id: "trouble", label: "عیب‌یابی" },
  ],
  en: [
    { id: "start", label: "Getting started" },
    { id: "vol", label: "Volume & invites" },
    { id: "apps", label: "Apps" },
    { id: "trouble", label: "Troubleshooting" },
  ],
};

export const FAQ_ITEMS: Record<Locale, FaqItem[]> = {
  fa: [
    { cat: "start", q: "کانفیگ رایگان چطور کار می‌کند؟", a: "هر بار که زمان کانفیگت تمام شود، یک کانفیگ رایگان تازه می‌گیری؛ لوکیشن را انتخاب کن، دکمه را بزن و لینک را در اپت وارد کن." },
    { cat: "start", q: "برای دریافت باید ثبت‌نام کنم؟", a: "نه. دریافت کاملاً بدون ثبت‌نام است و هیچ ایمیل یا شماره‌ای نمی‌خواهد." },
    { cat: "vol", q: "چطور حجم روزانه‌ام را بیشتر کنم؟", a: "با دعوت دوستان، نصب وب‌اپ و روشن‌کردن اعلان‌ها؛ هر کدام حجم روزانه‌ات را بیشتر می‌کند." },
    { cat: "vol", q: "اگر حجم امروزم تمام شود؟", a: "با یک دعوت موفق، همان کانفیگ همان لحظه دوباره فعال می‌شود." },
    { cat: "apps", q: "با چه اپ‌هایی کار می‌کند؟", a: "v2rayNG (اندروید)، Streisand (آیفون/مک) و Happ (همهٔ دستگاه‌ها)." },
    { cat: "apps", q: "روی ویندوز نصب می‌شود؟", a: "بله، با کلاینت Happ ویندوز." },
    { cat: "trouble", q: "وصل نمی‌شوم", a: "کانفیگ را دوباره بگیر، زمان دستگاه را چک کن و لوکیشن دیگری را امتحان کن." },
    { cat: "trouble", q: "سرعت کم است", a: "لوکیشن نزدیک‌تر را انتخاب کن و مطمئن شو حجم روزانه‌ات تمام نشده." },
    { cat: "trouble", q: "یک لوکیشن وصل نمی‌شود؛ باید تا کانفیگ بعدی صبر کنم؟", a: "نه. تا وقتی کانفیگت فعال است، از صفحهٔ «کانفیگ من» می‌توانی لوکیشن دیگری انتخاب کنی. لینک تازهٔ همان لوکیشن را در اپت وارد کن؛ حجم و زمان کانفیگ همان قبلی است." },
    { cat: "trouble", q: "روی اینترنت همراه هم کار می‌کند؟", a: "بله؛ کانفیگ به نوع اینترنت بستگی ندارد و روی وای‌فای و اینترنت همراه هر دو قابل استفاده است. اختلال‌ها ولی بین اپراتورها فرق دارد؛ اگر روی یکی وصل نشد، لوکیشن دیگری را امتحان کن." },
    { cat: "start", q: "چه اطلاعاتی از من نگه داشته می‌شود؟", a: "برای دریافت کانفیگ نام، ایمیل یا شماره نمی‌گیریم. این مرورگر با یک کوکی امضاشده شناخته می‌شود؛ یک اثر انگشت سبک مرورگر و هشی از محدودهٔ شبکه‌ات (نه خود IP) هم فقط برای جلوگیری از سوءاستفاده نگه داشته می‌شود، و حجم مصرفی کانفیگت برای سقف روزانه شمرده می‌شود. جزئیات در صفحهٔ حریم خصوصی است." },
    { cat: "trouble", q: "اگر سایت باز نشد، کانفیگم هم قطع می‌شود؟", a: "نه. کانفیگی که در اپت وارد کرده‌ای به این سایت وابسته نیست و تا پایان زمانش کار می‌کند. اگر قبلاً در همین مرورگر کانفیگ گرفته‌ای، آخرین لینکش برای صفحهٔ آفلاین سایت هم نگه داشته می‌شود." },
  ],
  en: [
    { cat: "start", q: "How does the free config work?", a: "Each time your config's time runs out you can claim a fresh free one; pick a location, press the button and import the link into your app." },
    { cat: "start", q: "Do I need to sign up?", a: "No. Claiming is entirely signup-free and needs no email or phone number." },
    { cat: "vol", q: "How do I grow my daily volume?", a: "By inviting friends, installing the web app and enabling notifications — each one adds to your daily volume." },
    { cat: "vol", q: "What if today's volume runs out?", a: "One successful invite revives the same config instantly." },
    { cat: "apps", q: "Which apps does it work with?", a: "v2rayNG (Android), Streisand (iOS/macOS) and Happ (all devices)." },
    { cat: "apps", q: "Can I install it on Windows?", a: "Yes, with the Happ Windows client." },
    { cat: "trouble", q: "I can't connect", a: "Re-claim the config, check your device clock and try a different location." },
    { cat: "trouble", q: "It's slow", a: "Pick a closer location and make sure your daily volume isn't used up." },
    { cat: "trouble", q: "A location won't connect — do I have to wait for my next config?", a: "No. While your config is active you can pick another location on the “My config” page. Import that location's new link into your app — your volume and time stay the same." },
    { cat: "trouble", q: "Does it work on mobile data?", a: "Yes — the config doesn't depend on the kind of connection, so it works on Wi-Fi and mobile data alike. Disruptions differ between carriers, though: if it won't connect on one, try another location." },
    { cat: "start", q: "What do you keep about me?", a: "We take no name, email or phone number to claim a config. This browser is recognised by a signed cookie; a light browser fingerprint and a hash of your network range (not the IP itself) are kept only to prevent abuse, and your config's usage is counted for the daily cap. The details are on the Privacy page." },
    { cat: "trouble", q: "If the site won't open, does my config stop working?", a: "No. A config you've imported into your app doesn't depend on this site and keeps working until its time is up. If you've claimed one in this browser before, its last link is kept for the site's offline page too." },
  ],
};

// ── Guides ────────────────────────────────────────────────────────────────────
// Every guide now targets Happ (one cross-platform app). Copy is extracted from the approved
// design; the per-platform difference is only the install source + the download button. Steps and
// troubleshooting are shared (the Happ flow is identical everywhere). Keep both `fa` and `en` in sync.
export const PLATFORMS = ["android", "ios", "windows", "macos", "linux"] as const;
export type Platform = (typeof PLATFORMS)[number];

export const APP_NAME = "Happ";

export interface GuideStep {
  t: string;
  d: string;
  /** this step is "get your config": it carries a link to the claim widget (C-29) */
  get?: true;
  /** a terminal command the step runs, drawn as its own left-to-right block under the download */
  cmd?: string;
}

// Locale-invariant platform metadata: the BrandIcon glyph key, the accent colour that tints the
// card/hero tile, the store glyph for the download button, and the OFFICIAL Happ download URL.
// Android's first button is the APK from Happ's own GitHub release (C-28, decision D4): Google Play
// serves nothing to an Iranian IP, so a guide that opened with it was a dead end at step one for the
// people it was written for. Play stays as the second option (`alt`). `appleId` marks the platforms
// whose only source is the App Store — which has no Iranian storefront, so the guide says how.
export interface PlatformMeta {
  os: "android" | "apple" | "windows" | "linux";
  acc: string;
  store: "android" | "googleplay" | "appstore" | "windows" | "linux";
  url: string;
  alt?: string;
  appleId?: true;
}
const APP_STORE = "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215";
export const PLATFORM_META: Record<Platform, PlatformMeta> = {
  android: {
    os: "android",
    acc: "#22B364",
    store: "android",
    url: "https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk",
    alt: "https://play.google.com/store/apps/details?id=com.happproxy&pcampaignid=web_share",
  },
  ios: { os: "apple", acc: "#5B6B82", store: "appstore", url: APP_STORE, appleId: true },
  windows: { os: "windows", acc: "#2A7BE4", store: "windows", url: "https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe" },
  macos: { os: "apple", acc: "#5B6B82", store: "appstore", url: APP_STORE, appleId: true },
  linux: { os: "linux", acc: "#E0872A", store: "linux", url: "https://github.com/Happ-proxy/happ-desktop/releases/latest/download/Happ.linux.x64.deb" },
};

export interface Guide extends PlatformMeta {
  platform: Platform;
  name: string;
  /** the page's meta description */
  desc: string;
  app: string;
  dl: { top: string; bottom: string };
  steps: GuideStep[];
  trouble: { q: string; a: string }[];
}

export const GUIDE_LABELS: Record<
  Locale,
  {
    title: string;
    sub: string;
    eyebrow: string;
    time: string;
    easy: string;
    view: string;
    steps: string;
    trouble: string;
    backToGuides: string;
    connect: string;
    get: string;
    storeAlt: string;
    appleId: string;
  }
> = {
  fa: {
    title: "راهنمای اتصال",
    sub: "سیستم‌عاملت را انتخاب کن و قدم‌به‌قدم با Happ وصل شو. همهٔ راهنماها کوتاه و ساده‌اند.",
    eyebrow: "راهنماها",
    time: "~۳ دقیقه",
    easy: "آسان",
    view: "مشاهدهٔ راهنما",
    steps: "مراحل",
    trouble: "عیب‌یابی",
    backToGuides: "همهٔ راهنماها",
    connect: "اتصال {name} با Happ",
    get: "کانفیگت را بگیر",
    storeAlt: "یا از Google Play",
    appleId:
      "اپ‌استور برای ایران فروشگاه ندارد؛ برای نصب Happ با یک Apple ID کشور دیگر (مثلاً آمریکا) وارد App Store شو.",
  },
  en: {
    title: "Setup guides",
    sub: "Pick your OS and connect step by step with Happ. Every guide is short and simple.",
    eyebrow: "Guides",
    time: "~3 min",
    easy: "Easy",
    view: "View guide",
    steps: "Steps",
    trouble: "Troubleshooting",
    backToGuides: "All guides",
    connect: "{name} with Happ",
    get: "Get your config",
    storeAlt: "or from Google Play",
    appleId:
      "The App Store has no Iranian storefront — to install Happ, sign in with an Apple ID from another country (for example the US).",
  },
};

// Each platform's own route through the same four moves — install, get the config, add it to Happ,
// connect. How an app gets onto the device, what the system asks on the first connect and what goes
// wrong afterwards are where the platforms really differ, and where a visitor gets stuck. All five
// guides used to share one text — 92–99% of each was word for word on another — so Google read them
// as one page and left two of them uncrawled. Step 2 links to the widget (it said «به صفحهٔ دریافت
// برو» and linked nowhere). On a phone step 3 leads with the one-tap Happ button; on a computer with
// the clipboard, which works whatever the browser does with a happ:// link. A UI label in Latin
// script is a path with «→» (`Settings → System`): an all-Latin run is laid out left to right inside
// Persian copy, where a «←» would point back up the path.
type Trouble = { q: string; a: string };

const GET: Record<Locale, { phone: GuideStep; computer: GuideStep }> = {
  fa: {
    phone: { t: "کانفیگت را بگیر", d: "در صفحهٔ اصلی لوکیشن دلخواهت را انتخاب کن و «دریافت کانفیگ» را بزن؛ کانفیگ همان لحظه ساخته می‌شود.", get: true },
    computer: { t: "کانفیگت را بگیر", d: "صفحهٔ اصلی را روی همین کامپیوتر باز کن، لوکیشن دلخواهت را انتخاب کن و «دریافت کانفیگ» را بزن تا لینک کانفیگ همین‌جا آماده باشد.", get: true },
  },
  en: {
    phone: { t: "Get your config", d: "On the home page, pick a location and tap “Get config” — your config is made on the spot.", get: true },
    computer: { t: "Get your config", d: "Open the home page on this computer, pick a location and click “Get config”, so the config link is right here.", get: true },
  },
};

const ADD_ON_COMPUTER: Record<Locale, GuideStep> = {
  fa: { t: "کانفیگ را به Happ اضافه کن", d: "زیر کانفیگ «کپی» را بزن و در Happ از دکمهٔ + گزینهٔ «Add from clipboard» را انتخاب کن. دکمهٔ Happ زیر کانفیگ را هم می‌توانی امتحان کنی؛ مرورگر اول می‌پرسد Happ باز شود یا نه." },
  en: { t: "Add it to Happ", d: "Under the config, click “Copy”, then in Happ press + and choose “Add from clipboard”. You can also try the Happ button under the config; the browser first asks whether to open Happ." },
};

const HAPP_STEPS: Record<Locale, Record<Platform, GuideStep[]>> = {
  fa: {
    android: [
      { t: "Happ را نصب کن", d: "روی دکمهٔ پایین بزن تا فایل نصبی (APK) دانلود شود و بعد بازش کن. اندروید بار اول می‌پرسد به مرورگرت اجازهٔ «نصب برنامه‌های ناشناس» را می‌دهی یا نه؛ اجازه بده و «نصب» را بزن." },
      GET.fa.phone,
      { t: "کانفیگ را به Happ اضافه کن", d: "زیر کانفیگ روی دکمهٔ Happ بزن تا با یک لمس به اپ اضافه شود. اگر اپ باز نشد، «کپی» را بزن و در Happ از دکمهٔ + گزینهٔ «Add from clipboard» را انتخاب کن." },
      { t: "وصل شو", d: "لوکیشن را انتخاب کن و روی دکمهٔ بزرگ اتصال بزن. بار اول اندروید «درخواست اتصال» VPN را نشان می‌دهد؛ «تأیید» را بزن. آیکون کلید بالای صفحه یعنی وصل شده‌ای." },
    ],
    ios: [
      { t: "Happ را نصب کن", d: "روی دکمهٔ پایین بزن تا صفحهٔ Happ در App Store باز شود و «Get» را بزن. اگر App Store گفت این اپ در کشور یا منطقهٔ تو در دسترس نیست، یعنی Apple ID تو ایرانی است؛ یادداشت زیر را ببین." },
      GET.fa.phone,
      { t: "کانفیگ را به Happ اضافه کن", d: "زیر کانفیگ روی دکمهٔ Happ بزن؛ Safari می‌پرسد صفحه در Happ باز شود یا نه، «Open» را بزن. اگر نشد، «کپی» را بزن و در Happ از دکمهٔ + گزینهٔ «Add from clipboard» را انتخاب کن؛ iOS برای خواندن کلیپ‌بورد اجازه می‌خواهد، «Allow Paste» را بزن." },
      { t: "وصل شو", d: "لوکیشن را انتخاب کن و روی دکمهٔ اتصال بزن. بار اول iOS می‌پرسد Happ می‌تواند پیکربندی VPN اضافه کند یا نه؛ «Allow» را بزن و با رمز گوشی یا Face ID تأیید کن. نشان VPN در نوار بالا یا Control Center یعنی وصل شده‌ای." },
    ],
    windows: [
      { t: "Happ را نصب کن", d: "روی دکمهٔ پایین بزن تا نصب‌کنندهٔ Happ (فایل exe) دانلود شود و اجرایش کن. اگر ویندوز پیام «Windows protected your PC» نشان داد، «More info» و بعد «Run anyway» را بزن؛ ویندوز این را دربارهٔ برنامه‌هایی می‌گوید که هنوز نمی‌شناسد." },
      GET.fa.computer,
      ADD_ON_COMPUTER.fa,
      { t: "وصل شو", d: "لوکیشن را انتخاب کن و روی دکمهٔ اتصال بزن. اگر ویندوز پرسید Happ به شبکه دسترسی داشته باشد یا نه، «Allow access» را بزن. بعد سایتی را که فیلتر بود در مرورگر باز کن تا مطمئن شوی وصلی." },
    ],
    macos: [
      { t: "Happ را نصب کن", d: "روی دکمهٔ پایین بزن تا صفحهٔ Happ در App Store مک باز شود و «Get» را بزن؛ بعد از نصب، Happ را از Launchpad یا پوشهٔ Applications باز کن." },
      GET.fa.computer,
      ADD_ON_COMPUTER.fa,
      { t: "وصل شو", d: "لوکیشن را انتخاب کن و روی دکمهٔ اتصال بزن. بار اول macOS می‌پرسد Happ می‌تواند پیکربندی VPN اضافه کند یا نه؛ «Allow» را بزن و رمز مک را وارد کن یا با Touch ID تأیید کن." },
    ],
    linux: [
      { t: "Happ را نصب کن", d: "روی دکمهٔ پایین بزن تا بستهٔ deb دانلود شود، بعد در ترمینال، در پوشه‌ای که فایل در آن ذخیره شده (معمولاً Downloads)، این دستور را اجرا کن. این بسته برای دبیان، اوبونتو و توزیع‌های بر پایهٔ آن‌هاست.", cmd: "sudo apt install ./Happ.linux.x64.deb" },
      GET.fa.computer,
      ADD_ON_COMPUTER.fa,
      { t: "وصل شو", d: "Happ را از فهرست برنامه‌ها باز کن، لوکیشن را انتخاب کن و روی دکمهٔ اتصال بزن. بعد سایتی را که فیلتر بود در مرورگر باز کن تا مطمئن شوی وصلی." },
    ],
  },
  en: {
    android: [
      { t: "Install Happ", d: "Tap the button below to download the installer (APK), then open it. The first time, Android asks whether your browser may “install unknown apps” — allow it, then tap “Install”." },
      GET.en.phone,
      { t: "Add it to Happ", d: "Under the config, tap the Happ button to add it in one tap. If the app doesn’t open, tap “Copy”, then in Happ press + and choose “Add from clipboard”." },
      { t: "Connect", d: "Pick a location and tap the big connect button. The first time, Android shows a VPN “Connection request” — tap “OK”. A key icon at the top of the screen means you’re connected." },
    ],
    ios: [
      { t: "Install Happ", d: "Tap the button below to open Happ in the App Store and tap “Get”. If the App Store says the app isn’t available in your country or region, your Apple ID is Iranian — see the note below." },
      GET.en.phone,
      { t: "Add it to Happ", d: "Under the config, tap the Happ button; Safari asks whether to open the page in Happ — tap “Open”. Otherwise tap “Copy”, then in Happ press + and choose “Add from clipboard”; iOS asks before Happ reads the clipboard — tap “Allow Paste”." },
      { t: "Connect", d: "Pick a location and tap connect. The first time, iOS asks whether Happ may add VPN configurations — tap “Allow” and confirm with your passcode or Face ID. The VPN badge in the status bar or Control Center means you’re connected." },
    ],
    windows: [
      { t: "Install Happ", d: "Click the button below to download the Happ installer (.exe) and run it. If Windows shows “Windows protected your PC”, click “More info”, then “Run anyway” — Windows says that about apps it doesn’t recognise yet." },
      GET.en.computer,
      ADD_ON_COMPUTER.en,
      { t: "Connect", d: "Pick a location and click connect. If Windows asks whether Happ may use the network, choose “Allow access”. Then open a site that was blocked in your browser to check you’re through." },
    ],
    macos: [
      { t: "Install Happ", d: "Click the button below to open Happ in the Mac App Store and click “Get”; once it’s installed, open Happ from Launchpad or the Applications folder." },
      GET.en.computer,
      ADD_ON_COMPUTER.en,
      { t: "Connect", d: "Pick a location and click connect. The first time, macOS asks whether Happ may add VPN configurations — click “Allow” and enter your Mac’s password or use Touch ID." },
    ],
    linux: [
      { t: "Install Happ", d: "Click the button below to download the .deb package, then run this command in a terminal, in the folder it was saved to (usually Downloads). The package is for Debian, Ubuntu and the distributions built on them.", cmd: "sudo apt install ./Happ.linux.x64.deb" },
      GET.en.computer,
      ADD_ON_COMPUTER.en,
      { t: "Connect", d: "Open Happ from your applications menu, pick a location and click connect. Then open a site that was blocked in your browser to check you’re through." },
    ],
  },
};

// Troubleshooting: what goes wrong on THIS platform first, then the two answers every Happ guide
// shares (a config that won't connect, a slow location).
const SHARED_TROUBLE: Record<Locale, Trouble[]> = {
  fa: [
    { q: "وصل نمی‌شود، چه کنم؟", a: "کانفیگ را دوباره از صفحهٔ دریافت کپی و در Happ import کن و مطمئن شو زمان دستگاهت درست تنظیم شده است." },
    { q: "سرعت پایین است", a: "لوکیشن دیگری را از صفحهٔ دریافت امتحان کن؛ لوکیشن نزدیک‌تر معمولاً سریع‌تر است." },
  ],
  en: [
    { q: "It won't connect, what do I do?", a: "Re-copy the config from the get page, re-import it in Happ and make sure your device time is set correctly." },
    { q: "It's slow", a: "Try another location from the get page; a closer location is usually faster." },
  ],
};

const TROUBLE: Record<Locale, Record<Platform, Trouble[]>> = {
  fa: {
    android: [
      { q: "فایل نصب نمی‌شود", a: "به برنامه‌ای که فایل را با آن باز کردی (مرورگر یا مدیر فایل) اجازهٔ «نصب برنامه‌های ناشناس» را بده: تنظیمات ← برنامه‌ها ← همان برنامه ← نصب برنامه‌های ناشناس. اگر Play Protect هشدار داد، «جزئیات بیشتر» و بعد «درهرصورت نصب شود» را بزن." },
      { q: "بعد از مدتی خودبه‌خود قطع می‌شود", a: "اندروید برای صرفه‌جویی در باتری برنامه‌های پس‌زمینه را می‌بندد. در تنظیمات ← برنامه‌ها ← Happ ← باتری، گزینهٔ «بدون محدودیت» را انتخاب کن؛ اسم این گزینه در گوشی‌های مختلف کمی فرق دارد." },
    ],
    ios: [
      { q: "Happ در App Store پیدا نمی‌شود", a: "App Store فقط اپ‌های کشورِ Apple ID تو را نشان می‌دهد و برای ایران فروشگاهی ندارد. با یک Apple ID کشور دیگر (مثلاً آمریکا) وارد App Store شو و دوباره روی دکمهٔ دانلود بزن." },
      { q: "اجازهٔ VPN را رد کردم", a: "در Happ دوباره روی دکمهٔ اتصال بزن تا iOS باز هم بپرسد و این بار «Allow» را بزن. پیکربندی Happ بعد از آن در Settings → General → VPN & Device Management دیده می‌شود." },
    ],
    windows: [
      { q: "ویندوز یا آنتی‌ویروس جلوی نصب را می‌گیرد", a: "از هشدار «Windows protected your PC» با «More info» و «Run anyway» رد شو. اگر آنتی‌ویروس فایل را پاک کرد، آن را فقط از همین دکمهٔ رسمی دوباره بگیر و در آنتی‌ویروس برایش استثنا بگذار." },
      { q: "نصب‌کننده روی کامپیوترم اجرا نمی‌شود", a: "این نصب‌کننده برای ویندوز ۶۴ بیتی است و روی ویندوز ۳۲ بیتی اجرا نمی‌شود. نوع ویندوزت را در Settings → System → About، جلوی System type ببین." },
    ],
    macos: [
      { q: "Happ در App Store مک پیدا نمی‌شود", a: "مثل آیفون، App Store مک هم برای ایران فروشگاه ندارد؛ با یک Apple ID کشور دیگر وارد شو. Happ روی مک و آیفون یک اپ است، پس همان Apple ID که روی آیفون استفاده کردی این‌جا هم کار می‌کند." },
      { q: "اجازهٔ VPN را ندادم", a: "در Happ دوباره روی دکمهٔ اتصال بزن تا macOS باز هم بپرسد. پیکربندی Happ بعد از آن در System Settings → VPN دیده می‌شود." },
    ],
    linux: [
      { q: "apt خطای وابستگی می‌دهد", a: "دستور sudo apt -f install را اجرا کن تا وابستگی‌های جاافتاده نصب شوند، بعد دستور نصب را دوباره بزن." },
      { q: "توزیع من بر پایهٔ دبیان نیست", a: "این بسته فقط روی دبیان، اوبونتو و توزیع‌های بر پایهٔ آن‌ها نصب می‌شود. برای توزیع‌های دیگر، صفحهٔ انتشار Happ desktop در GitHub را ببین." },
    ],
  },
  en: {
    android: [
      { q: "The file won't install", a: "Allow “Install unknown apps” for the app you opened the file with (your browser or file manager): Settings → Apps → that app → Install unknown apps. If Play Protect warns you, tap “More details”, then “Install anyway”." },
      { q: "It disconnects on its own after a while", a: "Android closes background apps to save battery. In Settings → Apps → Happ → Battery, choose “Unrestricted” — the name differs a little from phone to phone." },
    ],
    ios: [
      { q: "I can't find Happ in the App Store", a: "The App Store only shows the apps of your Apple ID's country, and it has no Iranian storefront. Sign in to the App Store with an Apple ID from another country (for example the US) and tap the download button again." },
      { q: "I declined the VPN permission", a: "Tap connect in Happ again so iOS asks once more, and choose “Allow” this time. Happ's configuration then shows under Settings → General → VPN & Device Management." },
    ],
    windows: [
      { q: "Windows or my antivirus blocks the installer", a: "Get past “Windows protected your PC” with “More info” and “Run anyway”. If your antivirus removes the file, download it again from this official button only and add an exception for it in the antivirus." },
      { q: "The installer won't run on my PC", a: "This installer is for 64-bit Windows and won't run on 32-bit Windows — check “System type” under Settings → System → About." },
    ],
    macos: [
      { q: "I can't find Happ in the Mac App Store", a: "As on the iPhone, the App Store has no Iranian storefront: sign in with an Apple ID from another country. Happ is one app on the Mac and the iPhone, so the Apple ID you used on your iPhone works here too." },
      { q: "I didn't allow the VPN", a: "Click connect in Happ again so macOS asks once more. Happ's configuration then appears under System Settings → VPN." },
    ],
    linux: [
      { q: "apt reports missing dependencies", a: "Run sudo apt -f install to pull in what's missing, then run the install command again." },
      { q: "My distribution isn't Debian-based", a: "This package installs only on Debian, Ubuntu and the distributions built on them. For others, check the Happ desktop releases page on GitHub." },
    ],
  },
};

// The guide's meta description, one per platform: a template with only the name swapped was one
// more sentence all five pages shared.
const GUIDE_DESC: Record<Locale, Record<Platform, string>> = {
  fa: {
    android: "راهنمای اتصال در اندروید با Happ: نصب فایل APK، افزودن کانفیگ رایگان GozarX با یک لمس، تأیید درخواست VPN و جلوگیری از قطع شدن در پس‌زمینه.",
    ios: "راهنمای اتصال در آیفون با Happ: نصب از App Store با Apple ID غیرایرانی، افزودن کانفیگ رایگان GozarX و اجازهٔ پیکربندی VPN.",
    windows: "راهنمای اتصال در ویندوز با Happ: اجرای نصب‌کنندهٔ exe و عبور از هشدار SmartScreen، افزودن کانفیگ رایگان GozarX و اتصال.",
    macos: "راهنمای اتصال در مک با Happ: نصب از App Store مک با Apple ID غیرایرانی، افزودن کانفیگ رایگان GozarX و اجازهٔ VPN.",
    linux: "راهنمای اتصال در لینوکس با Happ: نصب بستهٔ deb با apt، افزودن کانفیگ رایگان GozarX و رفع خطای وابستگی.",
  },
  en: {
    android: "Connect on Android with Happ: install the APK, add your free GozarX config in one tap, approve the VPN request and keep it from dropping in the background.",
    ios: "Connect on iPhone with Happ: install from the App Store with a non-Iranian Apple ID, add your free GozarX config and allow the VPN configuration.",
    windows: "Connect on Windows with Happ: run the .exe installer past the SmartScreen warning, add your free GozarX config and connect.",
    macos: "Connect on a Mac with Happ: install from the Mac App Store with a non-Iranian Apple ID, add your free GozarX config and allow the VPN.",
    linux: "Connect on Linux with Happ: install the .deb with apt, add your free GozarX config and fix missing dependencies.",
  },
};

const NAMES: Record<Locale, Record<Platform, string>> = {
  fa: { android: "اندروید", ios: "آیفون (iOS)", windows: "ویندوز", macos: "مک (macOS)", linux: "لینوکس" },
  en: { android: "Android", ios: "iPhone (iOS)", windows: "Windows", macos: "macOS", linux: "Linux" },
};

// Download-button label lines (small top line + bold bottom line), per platform + locale. A Persian
// line names the extension without its dot: «(.deb)» inside RTL text is drawn «(deb.)».
const DL: Record<Locale, Record<Platform, { top: string; bottom: string }>> = {
  fa: {
    android: { top: "دانلود مستقیم", bottom: "فایل نصبی اندروید (APK)" },
    ios: { top: "دریافت از", bottom: "App Store" },
    windows: { top: "دانلود مستقیم", bottom: "نصب‌کنندهٔ ویندوز (exe)" },
    macos: { top: "دریافت از", bottom: "App Store" },
    linux: { top: "دانلود مستقیم", bottom: "بستهٔ لینوکس (deb)" },
  },
  en: {
    android: { top: "Direct download", bottom: "Android installer (APK)" },
    ios: { top: "Download on the", bottom: "App Store" },
    windows: { top: "Direct download", bottom: "Windows installer (.exe)" },
    macos: { top: "Download on the", bottom: "App Store" },
    linux: { top: "Direct download", bottom: "Linux package (.deb)" },
  },
};

function isPlatform(p: string): p is Platform {
  return (PLATFORMS as readonly string[]).includes(p);
}

export function guideFor(locale: Locale, platform: string): Guide | undefined {
  if (!isPlatform(platform)) return undefined;
  return {
    platform,
    name: NAMES[locale][platform],
    desc: GUIDE_DESC[locale][platform],
    app: APP_NAME,
    dl: DL[locale][platform],
    steps: HAPP_STEPS[locale][platform],
    trouble: [...TROUBLE[locale][platform], ...SHARED_TROUBLE[locale]],
    ...PLATFORM_META[platform],
  };
}

export function guideList(locale: Locale): Guide[] {
  return PLATFORMS.map((p) => guideFor(locale, p)!);
}
