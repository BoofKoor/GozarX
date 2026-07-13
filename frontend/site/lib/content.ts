// Static content-page copy (about / legal / faq / guides), bilingual, in-code.
// Per CLAUDE.md the site keeps chrome + static copy in code (the DB `content` table holds bot copy
// and, later, admin-managed keyword landings — not these evergreen pages). Copy is extracted from
// the approved Phase-5 design mockup (docs/website/design/phase-5-content.html); the iOS/Windows/
// macOS/Linux guide steps are authored to match the Android/v2rayNG guide's shape (the mockup only
// detailed Android). Keep both `fa` and `en` in sync.

import type { Locale } from "@/lib/i18n";

// ── About ────────────────────────────────────────────────────────────────────
export const ABOUT: Record<Locale, { title: string; lead: string; body: string; deflect: string }> = {
  fa: {
    title: "دربارهٔ ما",
    lead: "GozarX یک ابزار رایگان است که هر روز به همه یک کانفیگ آزمایشی می‌دهد.",
    body: "هدف ما ساده است: دسترسی آزاد و بی‌دردسر، بدون ثبت‌نام و بدون هزینه. تیم کوچک ما روی سرعت، پایداری و حریم خصوصی تمرکز دارد.",
    deflect: "شاید جوابت این‌جا باشد:",
  },
  en: {
    title: "About us",
    lead: "GozarX is a free tool that hands everyone a trial config every day.",
    body: "Our goal is simple: open, hassle-free access with no signup and no cost. Our small team focuses on speed, stability and privacy.",
    deflect: "Your answer might be here:",
  },
};

// ── Legal (privacy / terms share one section shape) ───────────────────────────
export interface LegalSection {
  h: string;
  body: string;
  important?: boolean; // rendered as an emphasised "Important:" callout
}

export const LEGAL_UPDATED: Record<Locale, string> = {
  fa: "آخرین به‌روزرسانی: تیر ۱۴۰۴",
  en: "Last updated: July 2025",
};

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
      body: "هویت تو فقط با یک «شناسهٔ سبک روی همین مرورگر» ساخته می‌شود: یک کوکی امضاشده به‌همراه یک اثر انگشت سادهٔ مرورگر. این فقط برای این است که حجم روزانه و دعوت‌هایت را روی همین دستگاه به‌خاطر بسپاریم — نه برای شناسایی شخص تو.",
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
      body: "Your identity is just a “light token kept on this browser”: a signed cookie plus a simple browser fingerprint. It exists only so we can remember your daily volume and invites on this device — not to identify you personally.",
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
  { title: string; sub: string; search: string; empty: string; all: string; categories: string }
> = {
  fa: {
    title: "سوالات متداول",
    sub: "پاسخ سریع به پرتکرارترین سوال‌ها. اگر جوابت این‌جا نبود، از صفحهٔ تماس بپرس.",
    search: "جستجو در سوالات…",
    empty: "سوالی با این عبارت پیدا نشد.",
    all: "همه",
    categories: "دسته‌ها",
  },
  en: {
    title: "Frequently asked questions",
    sub: "Quick answers to the most common questions. If yours isn't here, ask on the contact page.",
    search: "Search questions…",
    empty: "No question matches that phrase.",
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
    { cat: "start", q: "کانفیگ رایگان چطور کار می‌کند؟", a: "هر ۲۴ ساعت یک کانفیگ رایگان می‌گیری؛ لوکیشن را انتخاب کن، دکمه را بزن و لینک را در اپت وارد کن." },
    { cat: "start", q: "برای دریافت باید ثبت‌نام کنم؟", a: "نه. دریافت کاملاً بدون ثبت‌نام است و هیچ ایمیل یا شماره‌ای نمی‌خواهد." },
    { cat: "vol", q: "چطور حجم روزانه‌ام را بیشتر کنم؟", a: "با دعوت دوستان، نصب وب‌اپ و روشن‌کردن اعلان‌ها — از بخش «حجم بیشتر»." },
    { cat: "vol", q: "اگر حجم امروزم تمام شود؟", a: "با یک دعوت موفق، همان کانفیگ همان لحظه دوباره فعال می‌شود." },
    { cat: "apps", q: "با چه اپ‌هایی کار می‌کند؟", a: "v2rayNG (اندروید)، Streisand (آیفون/مک) و Happ (همهٔ دستگاه‌ها)." },
    { cat: "apps", q: "روی ویندوز نصب می‌شود؟", a: "بله، با کلاینت Happ ویندوز." },
    { cat: "trouble", q: "وصل نمی‌شوم", a: "کانفیگ را دوباره بگیر، زمان دستگاه را چک کن و لوکیشن دیگری را امتحان کن." },
    { cat: "trouble", q: "سرعت کم است", a: "لوکیشن نزدیک‌تر را انتخاب کن و مطمئن شو حجم روزانه‌ات تمام نشده." },
  ],
  en: [
    { cat: "start", q: "How does the free config work?", a: "Every 24 hours you get a free config; pick a location, press the button and import the link into your app." },
    { cat: "start", q: "Do I need to sign up?", a: "No. Claiming is entirely signup-free and needs no email or phone number." },
    { cat: "vol", q: "How do I grow my daily volume?", a: "By inviting friends, installing the web app and enabling notifications — from the 'More volume' section." },
    { cat: "vol", q: "What if today's volume runs out?", a: "One successful invite revives the same config instantly." },
    { cat: "apps", q: "Which apps does it work with?", a: "v2rayNG (Android), Streisand (iOS/macOS) and Happ (all devices)." },
    { cat: "apps", q: "Can I install it on Windows?", a: "Yes, with the Happ Windows client." },
    { cat: "trouble", q: "I can't connect", a: "Re-claim the config, check your device clock and try a different location." },
    { cat: "trouble", q: "It's slow", a: "Pick a closer location and make sure your daily volume isn't used up." },
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
}

// Locale-invariant platform metadata: the BrandIcon glyph key, the accent colour that tints the
// card/hero tile, the store glyph for the download button, and the OFFICIAL Happ download URL.
export interface PlatformMeta {
  os: "android" | "apple" | "windows" | "linux";
  acc: string;
  store: "googleplay" | "appstore" | "windows" | "linux";
  url: string;
}
export const PLATFORM_META: Record<Platform, PlatformMeta> = {
  android: { os: "android", acc: "#22B364", store: "googleplay", url: "https://play.google.com/store/apps/details?id=com.happproxy&pcampaignid=web_share" },
  ios: { os: "apple", acc: "#5B6B82", store: "appstore", url: "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215" },
  windows: { os: "windows", acc: "#2A7BE4", store: "windows", url: "https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe" },
  macos: { os: "apple", acc: "#5B6B82", store: "appstore", url: "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215" },
  linux: { os: "linux", acc: "#E0872A", store: "linux", url: "https://github.com/Happ-proxy/happ-desktop/releases/latest/download/Happ.linux.x64.deb" },
};

export interface Guide extends PlatformMeta {
  platform: Platform;
  name: string;
  app: string;
  dl: { top: string; bottom: string };
  steps: GuideStep[];
  trouble: { q: string; a: string }[];
}

export const GUIDE_LABELS: Record<
  Locale,
  { title: string; sub: string; eyebrow: string; time: string; easy: string; view: string; steps: string; trouble: string; backToGuides: string; connect: string }
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
  },
};

// Shared Happ flow — identical on every platform (the install source differs only via the button).
const HAPP_STEPS: Record<Locale, GuideStep[]> = {
  fa: [
    { t: "Happ را نصب کن", d: "روی دکمهٔ پایین بزن تا Happ را دریافت و نصب کنی، سپس اپ را باز کن." },
    { t: "لینک کانفیگ را کپی کن", d: "به صفحهٔ دریافت برو، لوکیشن دلخواهت را بگیر و روی دکمهٔ «کپی» بزن تا لینک کانفیگ در کلیپ‌بورد قرار گیرد." },
    { t: "کانفیگ را از کلیپ‌بورد اضافه کن", d: "در Happ روی دکمهٔ + (افزودن) بزن و «Add from clipboard» را انتخاب کن؛ کانفیگ از کلیپ‌بورد شناسایی و اضافه می‌شود." },
    { t: "وصل شو", d: "لوکیشن را انتخاب کن و روی دکمهٔ بزرگ اتصال بزن؛ اگر اجازهٔ VPN خواسته شد آن را تأیید کن. چند لحظه بعد وصل می‌شوی." },
  ],
  en: [
    { t: "Install Happ", d: "Tap the button below to download and install Happ, then open the app." },
    { t: "Copy the config link", d: "Go to the get page, claim a location and press the “Copy” button so the config link is on your clipboard." },
    { t: "Add the config from clipboard", d: "In Happ tap the + (Add) button and choose “Add from clipboard”; the config is detected and added." },
    { t: "Connect", d: "Pick a location and tap the big connect button; approve the VPN permission if asked. You’ll be connected in a moment." },
  ],
};

// Shared troubleshooting (applies to every Happ guide).
const TROUBLE: Record<Locale, { q: string; a: string }[]> = {
  fa: [
    { q: "وصل نمی‌شود، چه کنم؟", a: "کانفیگ را دوباره از صفحهٔ دریافت کپی و در Happ import کن و مطمئن شو زمان دستگاهت درست تنظیم شده است." },
    { q: "سرعت پایین است", a: "لوکیشن دیگری را از صفحهٔ دریافت امتحان کن؛ لوکیشن نزدیک‌تر معمولاً سریع‌تر است." },
  ],
  en: [
    { q: "It won't connect, what do I do?", a: "Re-copy the config from the get page, re-import it in Happ and make sure your device time is set correctly." },
    { q: "It's slow", a: "Try another location from the get page; a closer location is usually faster." },
  ],
};

const NAMES: Record<Locale, Record<Platform, string>> = {
  fa: { android: "اندروید", ios: "آیفون (iOS)", windows: "ویندوز", macos: "مک (macOS)", linux: "لینوکس" },
  en: { android: "Android", ios: "iPhone (iOS)", windows: "Windows", macos: "macOS", linux: "Linux" },
};

// Download-button label lines (small top line + bold bottom line), per platform + locale.
const DL: Record<Locale, Record<Platform, { top: string; bottom: string }>> = {
  fa: {
    android: { top: "دریافت از", bottom: "Google Play" },
    ios: { top: "دریافت از", bottom: "App Store" },
    windows: { top: "دانلود مستقیم", bottom: "نصب‌کنندهٔ ویندوز (.exe)" },
    macos: { top: "دریافت از", bottom: "App Store" },
    linux: { top: "دانلود مستقیم", bottom: "بستهٔ لینوکس (.deb)" },
  },
  en: {
    android: { top: "Get it on", bottom: "Google Play" },
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
    app: APP_NAME,
    dl: DL[locale][platform],
    steps: HAPP_STEPS[locale],
    trouble: TROUBLE[locale],
    ...PLATFORM_META[platform],
  };
}

export function guideList(locale: Locale): Guide[] {
  return PLATFORMS.map((p) => guideFor(locale, p)!);
}
