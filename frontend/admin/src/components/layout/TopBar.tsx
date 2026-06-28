import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { logout } from "@/hooks/useAuth";
import { getUsername } from "@/lib/auth";

export function TopBar() {
  const username = getUsername() ?? "مدیر";
  const initial = username.charAt(0).toUpperCase();
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white/80 px-5 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
      <div className="flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand/10 text-sm font-bold text-brand">
          {initial}
        </div>
        <div className="text-sm text-slate-500 dark:text-slate-400">
          خوش آمدید،{" "}
          <span className="font-medium text-slate-800 dark:text-slate-200">{username}</span>
        </div>
      </div>
      <Button variant="ghost" size="sm" onClick={logout}>
        <LogOut className="h-4 w-4" />
        خروج
      </Button>
    </header>
  );
}
