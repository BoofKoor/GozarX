import { clsx } from "clsx";
import { NavLink } from "react-router-dom";

// Sub-navigation for the "Website" admin section (keeps the sidebar to one entry).
const TABS = [
  { to: "/site/settings", label: "تنظیمات" },
  { to: "/site/pages", label: "صفحه‌ها" },
  { to: "/site/inbox", label: "پیام‌ها" },
  { to: "/site/push", label: "اعلان‌ها" },
  { to: "/site/stats", label: "آمار" },
];

export function SiteTabs() {
  return (
    <div className="flex flex-wrap gap-1 border-b border-line">
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end
          className={({ isActive }) =>
            clsx(
              "-mb-px rounded-t-lg border-b-2 px-3 py-2 text-sm font-medium transition",
              isActive
                ? "border-brand text-brand"
                : "border-transparent text-content-muted hover:text-content",
            )
          }
        >
          {t.label}
        </NavLink>
      ))}
    </div>
  );
}
