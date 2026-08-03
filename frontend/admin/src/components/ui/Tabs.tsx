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

/** Route-driven tab bar (underline style) for a section's sub-navigation. */
export function NavTabs({ items, className }: { items: TabItem[]; className?: string }) {
  return (
    <div
      className={clsx(
        "scrollbar-thin -mb-px flex gap-1 overflow-x-auto border-b border-line",
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
              "flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition",
              isActive
                ? "border-brand text-brand"
                : "border-transparent text-content-muted hover:border-line-strong hover:text-content",
            )
          }
        >
          {t.icon && <t.icon className="h-4 w-4" />}
          {t.label}
          {typeof t.count === "number" && t.count > 0 && (
            <span className="rounded-full bg-brand/12 px-1.5 py-0.5 text-[10px] font-bold tabular-nums text-brand-700">
              {t.count}
            </span>
          )}
        </NavLink>
      ))}
    </div>
  );
}

/** Local (non-routed) tab bar for switching panels inside one page. */
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
      className={clsx("scrollbar-thin flex gap-1 overflow-x-auto border-b border-line", className)}
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
              "-mb-px flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition",
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
