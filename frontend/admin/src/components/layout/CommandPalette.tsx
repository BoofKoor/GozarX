import { clsx } from "clsx";
import { CornerDownLeft, LogOut, Moon, Search, Sun } from "lucide-react";
import { type ComponentType, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Modal } from "@/components/ui/Modal";
import { logout } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";

import { NAV_ITEMS } from "./nav";

interface Command {
  id: string;
  label: string;
  group: string;
  icon: ComponentType<{ className?: string }>;
  keywords: string[];
  run: () => void;
}

/** Case-insensitive subsequence-free "contains" over the label plus its keywords. */
function matches(cmd: Command, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  return (
    cmd.label.toLowerCase().includes(q) || cmd.keywords.some((k) => k.toLowerCase().includes(q))
  );
}

/**
 * ⌘K / Ctrl+K launcher. Every sidebar destination plus the two global actions (theme, sign out) in
 * one keyboard-reachable list — the panel previously had no way to move between sections without
 * the mouse, which is the main thing that made it feel unfinished next to the tools it sits beside.
 */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const navigate = useNavigate();
  const { isDark, toggle } = useTheme();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  const commands = useMemo<Command[]>(() => {
    const nav: Command[] = NAV_ITEMS.map((item) => ({
      id: `nav:${item.to}`,
      label: item.label,
      group: "رفتن به",
      icon: item.icon,
      keywords: item.keywords ?? [],
      run: () => navigate(item.to),
    }));
    return [
      ...nav,
      {
        id: "action:theme",
        label: isDark ? "پوستهٔ روشن" : "پوستهٔ تیره",
        group: "کارها",
        icon: isDark ? Sun : Moon,
        keywords: ["theme", "dark", "light", "پوسته", "تم"],
        run: toggle,
      },
      {
        id: "action:logout",
        label: "خروج از حساب",
        group: "کارها",
        icon: LogOut,
        keywords: ["logout", "sign out", "خروج"],
        run: logout,
      },
    ];
  }, [navigate, isDark, toggle]);

  const visible = useMemo(
    () => commands.filter((c) => matches(c, query.trim())),
    [commands, query],
  );

  // Reset the query and highlight each time the palette opens, and keep the cursor in range as the
  // filtered list shrinks under typing.
  useEffect(() => {
    if (open) {
      setQuery("");
      setCursor(0);
    }
  }, [open]);
  useEffect(() => {
    setCursor((c) => Math.min(c, Math.max(0, visible.length - 1)));
  }, [visible.length]);

  // Keep the highlighted row scrolled into view when navigating with the arrow keys.
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>('[data-active="true"]')?.scrollIntoView({
      block: "nearest",
    });
  }, [cursor]);

  if (!open) return null;

  const runAt = (index: number) => {
    const cmd = visible[index];
    if (!cmd) return;
    onOpenChange(false);
    cmd.run();
  };

  let lastGroup = "";

  return (
    <Modal
      onClose={() => onOpenChange(false)}
      className="max-w-lg overflow-hidden"
      labelledBy="cmdk-input"
    >
      <div className="flex items-center gap-2 border-b border-line px-4">
        <Search className="h-4 w-4 shrink-0 text-content-subtle" aria-hidden />
        <input
          id="cmdk-input"
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setCursor((c) => (c + 1) % Math.max(1, visible.length));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setCursor((c) => (c - 1 + visible.length) % Math.max(1, visible.length));
            } else if (e.key === "Enter") {
              e.preventDefault();
              runAt(cursor);
            }
          }}
          placeholder="جستجو در بخش‌ها و کارها…"
          aria-label="جستجوی فرمان"
          className="w-full bg-transparent py-3.5 text-sm text-content outline-none placeholder:text-content-subtle"
        />
        <kbd className="hidden shrink-0 rounded border border-line px-1.5 py-0.5 text-[10px] text-content-subtle sm:block">
          Esc
        </kbd>
      </div>

      {visible.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-content-muted">چیزی پیدا نشد.</p>
      ) : (
        <ul ref={listRef} role="listbox" className="scrollbar-thin max-h-80 overflow-y-auto p-2">
          {visible.map((cmd, i) => {
            const header = cmd.group !== lastGroup ? cmd.group : null;
            lastGroup = cmd.group;
            const active = i === cursor;
            return (
              <li key={cmd.id}>
                {header && (
                  <div className="px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-content-subtle">
                    {header}
                  </div>
                )}
                <button
                  type="button"
                  role="option"
                  aria-selected={active}
                  data-active={active}
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => runAt(i)}
                  className={clsx(
                    "flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-start text-sm transition",
                    active ? "bg-brand/10 text-brand-700" : "text-content hover:bg-surface-hover",
                  )}
                >
                  <cmd.icon
                    className={clsx(
                      "h-4 w-4 shrink-0",
                      active ? "text-brand" : "text-content-subtle",
                    )}
                  />
                  <span className="flex-1 truncate">{cmd.label}</span>
                  {active && (
                    <CornerDownLeft className="h-3.5 w-3.5 text-content-subtle" aria-hidden />
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Modal>
  );
}

/** Binds ⌘K / Ctrl+K globally. Ignored while typing so it never fights with a text field. */
export function useCommandPaletteShortcut(onOpen: () => void): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "k" && e.key !== "K") return;
      if (!e.metaKey && !e.ctrlKey) return;
      e.preventDefault();
      onOpen();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onOpen]);
}
