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

import type { MessageKey } from "@/i18n";

export interface NavItem {
  to: string;
  /** Catalogue key — the label is resolved at render time, so it follows the language. */
  labelKey: MessageKey;
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
  labelKey?: MessageKey;
  items: NavItem[];
}

/** The panel's navigation, grouped by product surface. Shared by the rail, the mobile drawer and
 *  the command palette so a new destination is added in exactly one place. */
export const NAV: NavGroup[] = [
  {
    items: [
      {
        to: "/",
        labelKey: "nav.dashboard",
        icon: LayoutDashboard,
        end: true,
        keywords: ["dashboard", "داشبورد", "آمار", "خانه"],
      },
    ],
  },
  {
    labelKey: "nav.group.bot",
    items: [
      {
        to: "/users",
        labelKey: "nav.users",
        icon: UsersIcon,
        keywords: ["users", "کاربران", "کاربر", "مسدود"],
      },
      {
        to: "/broadcast",
        labelKey: "nav.broadcast",
        icon: Megaphone,
        keywords: ["broadcast", "پیام همگانی", "ارسال", "فوروارد"],
      },
      {
        to: "/texts",
        labelKey: "nav.texts",
        icon: FileText,
        keywords: ["texts", "متن‌ها", "محتوا", "پیام"],
      },
      {
        to: "/buttons",
        labelKey: "nav.buttons",
        icon: MousePointerClick,
        keywords: ["buttons", "دکمه‌ها", "کیبورد", "منو"],
      },
      {
        to: "/settings",
        labelKey: "nav.settings",
        icon: SettingsIcon,
        keywords: ["settings", "تنظیمات", "اقتصاد", "حجم", "دعوت"],
      },
    ],
  },
  {
    labelKey: "nav.group.site",
    items: [
      {
        to: "/site",
        labelKey: "nav.site",
        icon: Globe,
        match: "/site",
        keywords: ["site", "وب‌سایت", "سایت", "صفحه", "اعلان", "پیام‌ها"],
      },
    ],
  },
  {
    labelKey: "nav.group.system",
    items: [
      {
        to: "/system",
        labelKey: "nav.system",
        icon: Activity,
        keywords: ["system", "health", "سلامت", "وضعیت", "منابع", "وبهوک"],
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
