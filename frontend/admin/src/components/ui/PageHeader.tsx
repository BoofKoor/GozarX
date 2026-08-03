import { clsx } from "clsx";
import type { ReactNode } from "react";

/**
 * The one page-title pattern. Before this, every page hand-rolled a bare `<h1 className="text-xl
 * font-bold ">`, so there was nowhere consistent to put a subtitle or the page's primary action and
 * the vertical rhythm drifted between screens.
 */
export function PageHeader({
  title,
  sub,
  actions,
  className,
  children,
}: {
  title: ReactNode;
  sub?: ReactNode;
  /** Primary/secondary buttons for the page, aligned to the end edge. */
  actions?: ReactNode;
  className?: string;
  /** Extra row rendered under the title — tabs, filter bars, range pickers. */
  children?: ReactNode;
}) {
  return (
    <div className={clsx("space-y-4", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-bold text-content">{title}</h1>
          {sub && <p className="mt-1 text-sm text-content-muted">{sub}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  );
}
