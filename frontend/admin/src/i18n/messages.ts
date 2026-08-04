/**
 * The panel's string catalogue.
 *
 * Two flat maps rather than one map of pairs, so a missing English string is a TYPE error: `EN` is
 * declared as `Record<keyof typeof FA, string>`, and TypeScript refuses the file until every key
 * the Persian side defines has a translation. A catalogue that can silently half-translate is a
 * catalogue that will.
 *
 * Keys are dotted and grouped by surface (`nav.*`, `shell.*`, …). Placeholders are `{token}` and
 * are substituted only when a value is supplied — the same convention the bot's `content` table
 * uses, so the two never need different mental models.
 *
 * Pages migrate their own literals into this file as they are rebuilt; what is here now is the
 * shell, which is what Phase B replaces.
 */

const FA = {
  // ── navigation ──────────────────────────────────────────────────────────
  "nav.dashboard": "داشبورد",
  "nav.users": "کاربران",
  "nav.broadcast": "پیام همگانی",
  "nav.texts": "متن‌ها",
  "nav.buttons": "دکمه‌ها",
  "nav.settings": "تنظیمات ربات",
  "nav.site": "وب‌سایت",
  "nav.system": "سلامت سرویس",
  "nav.group.bot": "ربات تلگرام",
  "nav.group.site": "وب‌سایت",
  "nav.group.system": "سیستم",

  // ── shell chrome ────────────────────────────────────────────────────────
  "shell.title": "پنل مدیریت",
  "shell.search": "جستجو…",
  "shell.searchAria": "جستجو و پیمایش سریع",
  "shell.openMenu": "باز کردن منو",
  "shell.closeMenu": "بستن منو",
  "shell.nav": "ناوبری",
  "shell.logout": "خروج",
  "shell.theme.toLight": "روشن‌کردن پوسته",
  "shell.theme.toDark": "تیره‌کردن پوسته",
  "shell.theme.title": "تغییر پوسته (Shift+D)",
  "shell.language": "زبان",
  "shell.health.ok": "سرویس سالم است",
  "shell.health.degraded": "سرویس با اختلال کار می‌کند",
  "shell.health.down": "سرویس دچار مشکل است",
  "shell.health.checking": "در حال بررسی وضعیت…",

  // ── command palette ─────────────────────────────────────────────────────
  "palette.placeholder": "جستجو در بخش‌ها و کارها…",
  "palette.aria": "جستجوی فرمان",
  "palette.empty": "چیزی پیدا نشد.",
  "palette.goto": "رفتن به",
  "palette.actions": "کارها",
  "palette.themeLight": "پوستهٔ روشن",
  "palette.themeDark": "پوستهٔ تیره",
  "palette.logout": "خروج از حساب",
  "palette.toEnglish": "Switch to English",
  "palette.toPersian": "تغییر به فارسی",

  // ── charts ──────────────────────────────────────────────────────────────
  "chart.trendLabel": "روند {days} روز اخیر",
  "chart.ratesLabel": "نرخ‌های کلیدی، بر حسب درصد",
  "chart.empty": "داده‌ای برای نمایش نیست",
} as const;

/** Same keys, English values. The annotation is what makes an omission fail to compile. */
const EN: Record<keyof typeof FA, string> = {
  "nav.dashboard": "Dashboard",
  "nav.users": "Users",
  "nav.broadcast": "Broadcast",
  "nav.texts": "Texts",
  "nav.buttons": "Buttons",
  "nav.settings": "Bot settings",
  "nav.site": "Website",
  "nav.system": "Service health",
  "nav.group.bot": "Telegram bot",
  "nav.group.site": "Website",
  "nav.group.system": "System",

  "shell.title": "Admin panel",
  "shell.search": "Search…",
  "shell.searchAria": "Search and jump",
  "shell.openMenu": "Open menu",
  "shell.closeMenu": "Close menu",
  "shell.nav": "Navigation",
  "shell.logout": "Sign out",
  "shell.theme.toLight": "Switch to the light theme",
  "shell.theme.toDark": "Switch to the dark theme",
  "shell.theme.title": "Toggle theme (Shift+D)",
  "shell.language": "Language",
  "shell.health.ok": "The service is healthy",
  "shell.health.degraded": "The service is degraded",
  "shell.health.down": "The service is down",
  "shell.health.checking": "Checking status…",

  "palette.placeholder": "Search sections and actions…",
  "palette.aria": "Search commands",
  "palette.empty": "Nothing matched.",
  "palette.goto": "Go to",
  "palette.actions": "Actions",
  "palette.themeLight": "Light theme",
  "palette.themeDark": "Dark theme",
  "palette.logout": "Sign out",
  "palette.toEnglish": "Switch to English",
  "palette.toPersian": "تغییر به فارسی",

  "chart.trendLabel": "Trend over the last {days} days",
  "chart.ratesLabel": "Key rates, as percentages",
  "chart.empty": "Nothing to show yet",
};

export type MessageKey = keyof typeof FA;

export const MESSAGES = { fa: FA, en: EN } as const;
