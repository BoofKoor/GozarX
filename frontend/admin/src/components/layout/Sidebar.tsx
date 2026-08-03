import { clsx } from "clsx";
import { PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";

import { BrandLockup } from "./Brand";
import { NAV, isItemActive, type NavItem } from "./nav";

function NavLinkItem({
  item,
  active,
  collapsed,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Link
      to={item.to}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      // Collapsed rail hides the text, so the native tooltip carries the name. A custom tooltip
      // would have to wrap the link in another focusable element — worse for keyboard users.
      title={collapsed ? item.label : undefined}
      className={clsx(
        "group relative flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition",
        collapsed && "justify-center px-0",
        active
          ? "bg-brand/10 text-brand-700"
          : "text-content-muted hover:bg-surface-hover hover:text-content",
      )}
    >
      {/* RTL: the active indicator sits on the START edge, which is the right-hand side. */}
      {active && (
        <span className="absolute inset-y-1.5 start-0 w-0.5 rounded-full bg-brand" aria-hidden />
      )}
      <item.icon
        className={clsx(
          "h-5 w-5 shrink-0 transition",
          active ? "text-brand" : "text-content-subtle",
        )}
      />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </Link>
  );
}

/** Shared nav body — used by both the desktop sidebar and the mobile drawer. `onNavigate` fires on
 *  a link click so the drawer can close itself. */
function SidebarNav({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const { pathname } = useLocation();
  return (
    <>
      <BrandLockup compact={collapsed} className={clsx("mb-6", collapsed && "justify-center")} />
      <nav className="scrollbar-thin -mx-1 flex-1 space-y-5 overflow-y-auto px-1">
        {NAV.map((group, i) => (
          <div key={group.label ?? `top-${i}`} className="space-y-1">
            {group.label && !collapsed && (
              <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-content-subtle">
                {group.label}
              </div>
            )}
            {group.label && collapsed && <div className="mx-2 my-2 h-px bg-line" aria-hidden />}
            {group.items.map((item) => (
              <NavLinkItem
                key={item.to}
                item={item}
                active={isItemActive(pathname, item)}
                collapsed={collapsed}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        ))}
      </nav>
    </>
  );
}

/** Desktop sidebar — static rail, hidden below md (the mobile drawer takes over there). */
export function Sidebar({
  collapsed,
  onToggleCollapsed,
}: {
  collapsed: boolean;
  onToggleCollapsed: () => void;
}) {
  return (
    <aside
      className={clsx(
        "hidden shrink-0 flex-col border-e border-line bg-nav p-4 transition-[width] duration-200 md:flex",
        collapsed ? "w-[76px]" : "w-60",
      )}
    >
      <SidebarNav collapsed={collapsed} />
      <button
        type="button"
        onClick={onToggleCollapsed}
        aria-label={collapsed ? "باز کردن نوار کناری" : "جمع‌کردن نوار کناری"}
        className={clsx(
          "mt-3 flex items-center gap-2 rounded-xl px-3 py-2 text-xs text-content-subtle transition hover:bg-surface-hover hover:text-content",
          collapsed && "justify-center px-0",
        )}
      >
        {collapsed ? (
          <PanelLeftOpen className="h-4 w-4" />
        ) : (
          <>
            <PanelLeftClose className="h-4 w-4" />
            جمع‌کردن منو
          </>
        )}
      </button>
    </aside>
  );
}

/** Mobile navigation drawer (below md). Slides in from the right (RTL), dims the page, and closes on
 *  overlay click, Esc, or navigation — the panel below md previously had NO navigation at all (M2). */
export function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { pathname } = useLocation();

  // Close whenever the route changes (covers programmatic navigation, not just link clicks).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => onClose(), [pathname]);

  // Esc-to-close + lock body scroll while the drawer is open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <div
      className={clsx("fixed inset-0 z-50 md:hidden", !open && "pointer-events-none")}
      aria-hidden={!open}
    >
      <div
        className={clsx(
          "absolute inset-0 bg-black/45 transition-opacity duration-200",
          open ? "opacity-100" : "opacity-0",
        )}
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="ناوبری"
        className={clsx(
          "absolute inset-y-0 end-0 flex w-64 flex-col border-s border-line bg-nav p-4 shadow-overlay transition-transform duration-200",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <button
          onClick={onClose}
          aria-label="بستن منو"
          className="absolute end-3 top-3 flex h-8 w-8 items-center justify-center rounded-lg text-content-subtle transition hover:bg-surface-hover hover:text-content"
        >
          <X className="h-5 w-5" />
        </button>
        <SidebarNav onNavigate={onClose} />
      </aside>
    </div>
  );
}
