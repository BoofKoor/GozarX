import { LogOut, Menu } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { logout } from "@/hooks/useAuth";
import { getUsername } from "@/lib/auth";

import { ThemeToggle } from "./ThemeToggle";

export function TopBar({ onMenuClick }: { onMenuClick: () => void }) {
  const username = getUsername() ?? "مدیر";
  const initial = username.charAt(0).toUpperCase();
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80 sm:px-5">
      <div className="flex items-center gap-2.5">
        <button
          onClick={onMenuClick}
          aria-label="باز کردن منو"
          className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 md:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand/10 text-sm font-bold text-brand">
          {initial}
        </div>
        <div className="text-sm text-slate-500 dark:text-slate-400">
          خوش آمدید،{" "}
          <span className="font-medium text-slate-800 dark:text-slate-200">{username}</span>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <ThemeToggle />
        <Button variant="ghost" size="sm" onClick={logout}>
          <LogOut className="h-4 w-4" />
          خروج
        </Button>
      </div>
    </header>
  );
}
