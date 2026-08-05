import { clsx } from "clsx";
import { LogOut, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";

import { useI18n } from "@/i18n";
import { logout } from "@/hooks/useAuth";

import { BrandLockup, BrandMark } from "./Brand";
import { NAV, isItemActive, type NavItem } from "./nav";

/**
 * One rail button.
 *
 * The active state is a BRAND TINT with no outline, not a neutral plate: the design marks the
 * current destination in the brand colour, and `bg-surface-hover` gave it the same grey a hover
 * produces, so the rail said "you are hovering here" where it meant "you are here".
 *
 * The marker beside it is a real element rather than a border, so it can sit clear of the button's
 * rounded corners. It is the height of the GLYPH, not of the button plus its outline, and it is
 * flush with the rail's inline-start edge — right in Persian, left in English. Floated a few pixels
 * inside the edge and stretched past the button it reads as a stray line rather than a tab marker.
 */
function RailButton({ item, active }: { item: NavItem; active: boolean }) {
  const { t } = useI18n();
  const label = t(item.labelKey);
  return (
    <Link
      to={item.to}
      aria-current={active ? "page" : undefined}
      title={label}
      aria-label={label}
      className={clsx(
        "relative grid h-10 w-10 shrink-0 place-items-center rounded-[13px] border transition",
        // Every item keeps its outline, not just the active one. Bare glyphs on the rail read as
        // decoration; the outlined squares are what make it a control strip.
        active
          ? "border-transparent bg-brand/15 text-brand"
          : "border-line text-content-muted hover:border-brand/40 hover:text-brand",
      )}
    >
      {active && (
        <span
          className="absolute -start-[14px] top-1/2 h-[26px] w-[3px] -translate-y-1/2 rounded-s-[3px] bg-brand"
          aria-hidden
        />
      )}
      <item.icon className="h-[18px] w-[18px]" />
    </Link>
  );
}

/** Desktop rail — icons only, generously spaced, hidden below md where the drawer takes over. */
export function Sidebar() {
  const { pathname } = useLocation();
  const { t } = useI18n();

  return (
    <nav
      aria-label={t("shell.nav")}
      // No divider. The rail and the well are different SURFACES, and that tone change is the seam
      // — a line on top of it draws the eye to the joint instead of to the two planes.
      className="hidden w-[68px] shrink-0 flex-col items-center gap-3 bg-nav pb-[22px] pt-[18px] md:flex"
    >
      <BrandMark className="mb-6 h-8 w-8" />
      {NAV.flatMap((group) => group.items).map((item) => (
        <RailButton key={item.to} item={item} active={isItemActive(pathname, item)} />
      ))}
      <span className="flex-1" />
      <button
        type="button"
        onClick={logout}
        title={t("shell.logout")}
        aria-label={t("shell.logout")}
        className="grid h-10 w-10 place-items-center rounded-[13px] border border-line text-content-muted transition hover:border-brand/40 hover:text-brand"
      >
        <LogOut className="h-[18px] w-[18px]" />
      </button>
    </nav>
  );
}

/** Mobile navigation drawer (below md). Slides in from the inline-end, dims the page, and closes on
 *  overlay click, Esc, or navigation. Labels are shown here — there is room, and a bare icon strip
 *  on a phone is a guessing game. */
export function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { pathname } = useLocation();
  const { t } = useI18n();
  const shellRef = useRef<HTMLDivElement>(null);

  // `inert`, not just `aria-hidden`. The closed drawer stays mounted so it can slide, and
  // `pointer-events-none` only stops the MOUSE — every link inside remained in the tab order, so on
  // a phone Tab walked through ten invisible nav items before reaching the page. (An `aria-hidden`
  // subtree containing focusables is an ARIA violation for exactly this reason: focus lands on
  // something the screen reader announces as nothing.) `inert` removes both at once.
  useEffect(() => {
    const el = shellRef.current;
    if (!el) return;
    if (open) el.removeAttribute("inert");
    else el.setAttribute("inert", "");
  }, [open]);

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
      ref={shellRef}
      className={clsx("fixed inset-0 z-50 md:hidden", !open && "pointer-events-none")}
      aria-hidden={!open}
    >
      <div
        className={clsx(
          "absolute inset-0 bg-black/45 backdrop-blur-sm transition-opacity duration-200",
          open ? "opacity-100" : "opacity-0",
        )}
        onClick={onClose}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={t("shell.nav")}
        className={clsx(
          "absolute inset-y-0 end-0 flex w-64 flex-col border-s border-line bg-nav p-4 shadow-overlay transition-transform duration-200",
          open ? "translate-x-0" : "rtl:-translate-x-full ltr:translate-x-full",
        )}
      >
        <button
          onClick={onClose}
          aria-label={t("shell.closeMenu")}
          className="absolute end-3 top-3 flex h-8 w-8 items-center justify-center rounded-lg text-content-subtle transition hover:bg-surface-hover hover:text-content"
        >
          <X className="h-5 w-5" />
        </button>
        <BrandLockup className="mb-6" />
        <div className="scrollbar-thin -mx-1 flex-1 space-y-5 overflow-y-auto px-1">
          {NAV.map((group, i) => (
            <div key={group.labelKey ?? `top-${i}`} className="space-y-1">
              {group.labelKey && (
                <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-content-subtle">
                  {t(group.labelKey)}
                </div>
              )}
              {group.items.map((item) => {
                const active = isItemActive(pathname, item);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    onClick={onClose}
                    aria-current={active ? "page" : undefined}
                    className={clsx(
                      "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition",
                      active
                        ? "bg-brand/15 text-brand-700"
                        : "text-content-muted hover:bg-surface-hover hover:text-content",
                    )}
                  >
                    <item.icon
                      className={clsx(
                        "h-5 w-5 shrink-0",
                        active ? "text-brand" : "text-content-subtle",
                      )}
                    />
                    <span className="truncate">{t(item.labelKey)}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
