import { clsx } from "clsx";
import type { ComponentType, ReactNode } from "react";
import { NavLink } from "react-router-dom";

export interface TabItem {
  to: string;
  label: ReactNode;
  icon?: ComponentType<{ className?: string }>;
  /** Small trailing count (unread messages, draft pages). Hidden when 0/undefined. */
  count?: number;
}

/**
 * Route-driven tab bar (underline style) for a section's sub-navigation.
 *
 * `overflow-y-hidden` is not redundant beside `overflow-x-auto`: when one axis is not `visible` the
 * other computes from `visible` to `auto`, so a strip that overflows its content box by a single
 * pixel — which this one does, by exactly the 1px the underline overlap costs — becomes a VERTICAL
 * scroll container. Under overlay scrollbars that is invisible; on Windows it draws a stubby
 * scrollbar with arrows beside the tabs. Naming the axis is the whole fix.
 */
export function NavTabs({ items, className }: { items: TabItem[]; className?: string }) {
  return (
    <div
      className={clsx(
        "scrollbar-thin -mb-px flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line",
        className,
      )}
    >
      {items.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end
          className={({ isActive }) =>
            clsx(
              "flex shrink-0 items-center gap-2 border-b-2 px-3 py-2 text-[0.8rem] font-medium transition",
              isActive
                ? "border-brand text-brand"
                : "border-transparent text-content-muted hover:border-line-strong hover:text-content",
            )
          }
        >
          {t.icon && <t.icon className="h-4 w-4" />}
          {t.label}
          {typeof t.count === "number" && t.count > 0 && (
            <span className="rounded-full bg-brand/15 px-1.5 py-0.5 text-[10px] font-bold tabular-nums text-brand-700">
              {t.count}
            </span>
          )}
        </NavLink>
      ))}
    </div>
  );
}

/** Local (non-routed) tab bar for switching panels inside one page. Same axis note as `NavTabs`. */
export function Tabs<T extends string>({
  value,
  onChange,
  items,
  className,
}: {
  value: T;
  onChange: (next: T) => void;
  items: { value: T; label: ReactNode; icon?: ComponentType<{ className?: string }> }[];
  className?: string;
}) {
  return (
    <div
      role="tablist"
      className={clsx(
        "scrollbar-thin -mb-px flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line",
        className,
      )}
    >
      {items.map((t) => {
        const active = t.value === value;
        return (
          <button
            key={t.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(t.value)}
            className={clsx(
              // The underline overlap belongs to the STRIP, not to each tab — as it already does in
              // `NavTabs`. Carried on the tab, its negative margin shortened the strip's content box
              // to 1px LESS than the tabs standing in it, which both clipped the active tab's 2px
              // underline to 1px and made the strip a vertical scroll container.
              "flex shrink-0 items-center gap-2 border-b-2 px-3 py-2 text-[0.8rem] font-medium transition",
              active
                ? "border-brand text-brand"
                : "border-transparent text-content-muted hover:border-line-strong hover:text-content",
            )}
          >
            {t.icon && <t.icon className="h-4 w-4" />}
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
