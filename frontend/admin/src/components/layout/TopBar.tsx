import { clsx } from "clsx";
import { LogOut, Menu, Search } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/Button";
import { logout } from "@/hooks/useAuth";
import { useSystemHealth } from "@/hooks/useSystem";
import { getUsername } from "@/lib/auth";

import { NAV_ITEMS, isItemActive } from "./nav";
import { ThemeToggle } from "./ThemeToggle";

const STATUS: Record<string, { tone: string; label: string }> = {
  ok: { tone: "bg-success-500", label: "سرویس سالم است" },
  degraded: { tone: "bg-warning-500", label: "سرویس با اختلال کار می‌کند" },
  down: { tone: "bg-danger-500", label: "سرویس دچار مشکل است" },
};

/** Live status dot linking to the System page — the health snapshot is already polled every 10s
 *  there, and react-query shares the one query, so this costs no extra requests. */
function HealthDot() {
  const { data } = useSystemHealth();
  const state = STATUS[data?.status ?? ""] ?? {
    tone: "bg-content-subtle",
    label: "در حال بررسی وضعیت…",
  };
  return (
    <Link
      to="/system"
      title={state.label}
      aria-label={state.label}
      className="flex h-9 w-9 items-center justify-center rounded-xl transition hover:bg-surface-hover"
    >
      <span className="relative flex h-2.5 w-2.5">
        {data?.status === "ok" && (
          <span
            className={clsx(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-70",
              state.tone,
            )}
          />
        )}
        <span className={clsx("relative inline-flex h-2.5 w-2.5 rounded-full", state.tone)} />
      </span>
    </Link>
  );
}

export function TopBar({
  onMenuClick,
  onSearchClick,
}: {
  onMenuClick: () => void;
  onSearchClick: () => void;
}) {
  const username = getUsername() ?? "مدیر";
  const initial = username.charAt(0).toUpperCase();
  const { pathname } = useLocation();
  const current = NAV_ITEMS.find((item) => isItemActive(pathname, item));

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-line bg-nav/85 px-4 py-2.5 backdrop-blur sm:px-6">
      <div className="flex min-w-0 items-center gap-2">
        <button
          onClick={onMenuClick}
          aria-label="باز کردن منو"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-content-muted transition hover:bg-surface-hover hover:text-content md:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        {/* Section name — orients you after a deep link or a browser back, which the old bar
            ("خوش آمدید، …") never did. */}
        <span className="truncate text-sm font-medium text-content">
          {current?.label ?? "پنل مدیریت"}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <button
          onClick={onSearchClick}
          aria-label="جستجو و پیمایش سریع"
          className="flex h-9 items-center gap-2 rounded-xl border border-line px-2.5 text-xs text-content-subtle transition hover:bg-surface-hover hover:text-content"
        >
          <Search className="h-4 w-4" />
          <span className="hidden sm:inline">جستجو…</span>
          <kbd
            className="hidden rounded border border-line px-1 py-0.5 text-[10px] sm:inline"
            dir="ltr"
          >
            ⌘K
          </kbd>
        </button>
        <HealthDot />
        <ThemeToggle />
        <div className="mx-1 hidden h-6 w-px bg-line sm:block" aria-hidden />
        <div
          className="hidden h-8 w-8 items-center justify-center rounded-full bg-brand/10 text-xs font-bold text-brand-700 sm:flex"
          title={username}
        >
          {initial}
        </div>
        <Button variant="ghost" size="sm" onClick={logout} aria-label="خروج">
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">خروج</span>
        </Button>
      </div>
    </header>
  );
}
