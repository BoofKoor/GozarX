import { clsx } from "clsx";
import { LayoutDashboard, Settings as SettingsIcon } from "lucide-react";
import { NavLink } from "react-router-dom";

const items = [
  { to: "/", label: "داشبورد", icon: LayoutDashboard },
  { to: "/settings", label: "تنظیمات", icon: SettingsIcon },
];

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 border-l border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 md:block">
      <div className="mb-6 px-2 text-lg font-bold text-brand">GozarX</div>
      <nav className="space-y-1">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition",
                isActive
                  ? "bg-brand/10 text-brand"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
              )
            }
          >
            <Icon className="h-5 w-5" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
