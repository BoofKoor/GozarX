import {
  Activity,
  FileText,
  Globe,
  LayoutDashboard,
  Megaphone,
  MousePointerClick,
  Settings as SettingsIcon,
  Users as UsersIcon,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Match the whole section rather than the exact path (the Website tabs all live under /site/*). */
  match?: string;
  /** Match ONLY this exact path (the dashboard at "/", which every path starts with). */
  end?: boolean;
  /** Extra words the command palette should match on — Persian synonyms and the English name. */
  keywords?: string[];
}

export interface NavGroup {
  /** Undefined for the top-level items that sit above the first labelled group. */
  label?: string;
  items: NavItem[];
}

/** The panel's navigation, grouped by product surface. Shared by the sidebar, the mobile drawer and
 *  the command palette so a new destination is added in exactly one place. */
export const NAV: NavGroup[] = [
  {
    items: [
      {
        to: "/",
        label: "داشبورد",
        icon: LayoutDashboard,
        end: true,
        keywords: ["dashboard", "آمار", "خانه"],
      },
    ],
  },
  {
    label: "ربات تلگرام",
    items: [
      { to: "/users", label: "کاربران", icon: UsersIcon, keywords: ["users", "کاربر", "مسدود"] },
      {
        to: "/broadcast",
        label: "پیام همگانی",
        icon: Megaphone,
        keywords: ["broadcast", "ارسال", "فوروارد"],
      },
      { to: "/texts", label: "متن‌ها", icon: FileText, keywords: ["texts", "محتوا", "پیام"] },
      {
        to: "/buttons",
        label: "دکمه‌ها",
        icon: MousePointerClick,
        keywords: ["buttons", "کیبورد", "منو"],
      },
      {
        to: "/settings",
        label: "تنظیمات ربات",
        icon: SettingsIcon,
        keywords: ["settings", "اقتصاد", "حجم", "دعوت"],
      },
    ],
  },
  {
    label: "وب‌سایت",
    items: [
      {
        to: "/site/settings",
        label: "وب‌سایت",
        icon: Globe,
        match: "/site",
        keywords: ["site", "سایت", "صفحه", "اعلان", "پیام‌ها"],
      },
    ],
  },
  {
    label: "سیستم",
    items: [
      {
        to: "/system",
        label: "سلامت سرویس",
        icon: Activity,
        keywords: ["system", "health", "وضعیت", "منابع", "وبهوک"],
      },
    ],
  },
];

/** Flat list of every destination — what the command palette searches. */
export const NAV_ITEMS: NavItem[] = NAV.flatMap((g) => g.items);

export function isItemActive(pathname: string, item: NavItem): boolean {
  if (item.match) return pathname === item.match || pathname.startsWith(`${item.match}/`);
  if (item.end) return pathname === item.to;
  return pathname === item.to || pathname.startsWith(`${item.to}/`);
}
