import { clsx } from "clsx";
import type { ReactNode } from "react";

/** A titled section divider used to group a long page into scannable bands. */
export function Section({
  title,
  sub,
  action,
  className,
}: {
  title: string;
  sub?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("flex items-center gap-3 pt-2", className)}>
      <div className="shrink-0">
        <h2 className="text-sm font-semibold text-content">{title}</h2>
        {sub && <p className="text-xs text-content-muted">{sub}</p>}
      </div>
      <div className="h-px flex-1 bg-line" />
      {action}
    </div>
  );
}
