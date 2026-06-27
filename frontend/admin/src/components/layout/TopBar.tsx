import { LogOut } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { logout } from "@/hooks/useAuth";
import { getUsername } from "@/lib/auth";

export function TopBar() {
  const username = getUsername() ?? "مدیر";
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="text-sm text-slate-500 dark:text-slate-400">
        خوش آمدید،{" "}
        <span className="font-medium text-slate-800 dark:text-slate-200">{username}</span>
      </div>
      <Button variant="ghost" onClick={logout}>
        <LogOut className="h-4 w-4" />
        خروج
      </Button>
    </header>
  );
}
