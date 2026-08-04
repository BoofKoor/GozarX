import { useCallback, useState } from "react";
import { Outlet } from "react-router-dom";

import { CommandPalette, useCommandPaletteShortcut } from "./CommandPalette";
import { MobileNav, Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

/**
 * The console: a fixed icon rail, a top bar, and a content WELL.
 *
 * The well is a distinct surface (`bg-surface-sunken`) rather than the page background, so cards
 * read as sitting ON something. The collapse toggle is gone with it — the rail is icons only now,
 * so there is nothing left to collapse, and a control whose two states look the same is noise.
 */
export function AppShell() {
  const [navOpen, setNavOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useCommandPaletteShortcut(useCallback(() => setPaletteOpen(true), []));

  return (
    <div className="flex h-screen bg-canvas">
      <Sidebar />
      <MobileNav open={navOpen} onClose={() => setNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onMenuClick={() => setNavOpen(true)} onSearchClick={() => setPaletteOpen(true)} />
        <main className="scrollbar-thin flex-1 overflow-y-auto bg-surface-sunken p-4 sm:p-6">
          <div className="animate-fade-in mx-auto w-full max-w-[1180px]">
            <Outlet />
          </div>
        </main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}
