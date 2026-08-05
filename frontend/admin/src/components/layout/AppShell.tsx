import { clsx } from "clsx";
import { useCallback, useState } from "react";
import { Outlet } from "react-router-dom";

import { CommandPalette, useCommandPaletteShortcut } from "./CommandPalette";
import { ChromeProvider, SIDE_STACK, SIDE_WIDTH, useChrome } from "./chrome";
import { MobileNav, Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

/**
 * The console: an icon rail and a content WELL inside ONE rounded panel, with the dashboard's live
 * figures in a second panel beside it, both floating on the page ground.
 *
 * That framing is the design's, and it is doing work: the rail and the well are two surfaces of a
 * single object, so the seam between them is a tone change rather than a rule, and the gutter around
 * the whole thing is what stops a dense operator console from reading as a wall. Edge to edge with a
 * bordered rail, the same components read flat.
 *
 * `overflow-hidden` on the panel is what lets the rail and the well share its rounded corners
 * without either of them repeating the radius.
 */
function Shell() {
  const [navOpen, setNavOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const chrome = useChrome();

  useCommandPaletteShortcut(useCallback(() => setPaletteOpen(true), []));

  return (
    <div className="flex h-screen gap-3 bg-canvas p-0 sm:p-3">
      <div className="flex min-w-0 flex-1 overflow-hidden bg-nav shadow-raised sm:rounded-2xl">
        <Sidebar />
        <MobileNav open={navOpen} onClose={() => setNavOpen(false)} />
        <div className="flex min-w-0 flex-1 flex-col bg-surface-sunken">
          <TopBar onMenuClick={() => setNavOpen(true)} onSearchClick={() => setPaletteOpen(true)} />
          <main className="scrollbar-thin flex-1 overflow-y-auto px-4 pb-6 pt-3 sm:px-5">
            <div className="animate-fade-in mx-auto w-full max-w-[1180px]">
              <Outlet />
            </div>
          </main>
        </div>
      </div>

      {/* The second panel. Always MOUNTED so a page has somewhere to portal to, but it only takes
          up space once a page has claimed it — and never below the width where it would steal the
          console's height instead of sitting beside it.

          `SIDE_STACK` brings the `[&>*]:shrink-0` this needs to overflow rather than squeeze; the
          `hidden`/`flex` pair below still decides whether it lays out at all. */}
      <aside
        ref={chrome?.setSideHost}
        className={clsx(
          "scrollbar-thin shrink-0 overflow-y-auto rounded-2xl bg-surface p-4 shadow-raised",
          SIDE_WIDTH,
          SIDE_STACK,
          chrome?.sideFilled ? "hidden xl:flex" : "hidden",
        )}
      />

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  );
}

export function AppShell() {
  return (
    <ChromeProvider>
      <Shell />
    </ChromeProvider>
  );
}
