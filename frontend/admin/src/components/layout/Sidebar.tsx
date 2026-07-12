import { clsx } from "clsx";
import {
  Activity,
  FileText,
  Globe,
  LayoutDashboard,
  Megaphone,
  MousePointerClick,
  Settings as SettingsIcon,
  Users as UsersIcon,
  Zap,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

// `match` highlights the item on a whole section (the Website tabs live under /site/*); items
// without it match their exact path (or a nested child of it).
const items = [
  { to: "/", label: "داشبورد", icon: LayoutDashboard, end: true },
  { to: "/users", label: "کاربران", icon: UsersIcon },
  { to: "/broadcast", label: "پیام همگانی", icon: Megaphone },
  { to: "/texts", label: "متن‌ها", icon: FileText },
  { to: "/buttons", label: "دکمه‌ها", icon: MousePointerClick },
  { to: "/system", label: "سیستم", icon: Activity },
  { to: "/settings", label: "تنظیمات", icon: SettingsIcon },
  { to: "/site/settings", label: "وب‌سایت", icon: Globe, match: "/site" },
];

function isItemActive(pathname: string, to: string, end?: boolean, match?: string): boolean {
  if (match) return pathname === match || pathname.startsWith(`${match}/`);
  if (end) return pathname === to;
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function Sidebar() {
  const { pathname } = useLocation();
  return (
    <aside className="hidden w-60 shrink-0 border-l border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 md:flex md:flex-col">
      <div className="mb-7 flex items-center gap-2.5 px-1">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand text-white shadow-sm">
          <Zap className="h-5 w-5" />
        </div>
        <div className="leading-tight">
          <div className="text-base font-bold text-slate-800 dark:text-slate-100">GozarX</div>
          <div className="text-[11px] text-slate-400">پنل مدیریت</div>
        </div>
      </div>
      <nav className="space-y-1">
        {items.map(({ to, label, icon: Icon, end, match }) => {
          const active = isItemActive(pathname, to, end, match);
          return (
            <Link
              key={to}
              to={to}
              aria-current={active ? "page" : undefined}
              className={clsx(
                "group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition",
                active
                  ? "bg-brand/10 text-brand-700 dark:text-brand-200"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
              )}
            >
              <Icon
                className={clsx(
                  "h-5 w-5 transition",
                  active ? "text-brand" : "text-slate-400 group-hover:text-slate-500",
                )}
              />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto px-1 pt-4 text-[11px] text-slate-300 dark:text-slate-600">
        نسخه ۲ · Gozar
      </div>
    </aside>
  );
}
