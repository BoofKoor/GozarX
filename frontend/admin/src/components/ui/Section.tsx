import { clsx } from "clsx";
import type { ReactNode } from "react";

/**
 * A titled section divider used to group a long page into scannable bands.
 *
 * The title block WRAPS rather than holding its width. As `shrink-0` it could not give way, so on
 * a phone a long title plus its sub plus a trailing badge measured 460px inside a 358px column —
 * and because `<main>` scrolls vertically, the browser computes the other axis from `visible` to
 * `auto` too, which turned that into the whole page sliding sideways by 85px. `document.scrollWidth`
 * stays at the viewport width throughout, so nothing at the document level reports it.
 *
 * The rule keeps `flex-1` but is hidden below `sm`: at 358px there is nothing left for it to fill,
 * and a 0px rule between two wrapped lines is just an invisible flex item taking a gap.
 */
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
    <div className={clsx("flex flex-wrap items-center gap-x-3 gap-y-1 pt-2", className)}>
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-content">{title}</h2>
        {sub && <p className="text-xs text-content-muted">{sub}</p>}
      </div>
      <div className="hidden h-px flex-1 bg-line sm:block" />
      {action}
    </div>
  );
}
