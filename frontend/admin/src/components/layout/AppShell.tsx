import { useState } from "react";
import { Outlet } from "react-router-dom";

import { MobileNav, Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell() {
  const [navOpen, setNavOpen] = useState(false);
  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950">
      <Sidebar />
      <MobileNav open={navOpen} onClose={() => setNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onMenuClick={() => setNavOpen(true)} />
        <main className="scrollbar-thin flex-1 overflow-y-auto p-4 sm:p-6">
          <div className="mx-auto w-full max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
