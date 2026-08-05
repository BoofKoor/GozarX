import { clsx } from "clsx";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

import { useChrome } from "@/components/layout/chrome";

/**
 * The one page-title pattern. Before this, every page hand-rolled a bare `<h1 className="text-xl
 * font-bold ">`, so there was nowhere consistent to put a subtitle or the page's primary action and
 * the vertical rhythm drifted between screens.
 *
 * The title and its sub-line are PORTALLED into the top bar, where the design keeps them. Rendered
 * in both places the console said its own name twice in a column — a `bg-nav` strip with the
 * section name, then the same words again as an `<h1>` — and spent two horizontal bands and about
 * 105px before any content. The page still owns them: it decides the wording, and a page without a
 * shell around it (login, the setup wizard) falls back to rendering them in place.
 *
 * `title` and `sub` therefore have to be renderable in a bar: keep them to text.
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
  const chrome = useChrome();

  const heading = (
    <div className="min-w-0">
      <h1 className="truncate text-base font-bold leading-tight text-content">{title}</h1>
      {sub && <p className="truncate text-xs text-content-subtle">{sub}</p>}
    </div>
  );

  return (
    <div className={clsx("space-y-4", className)}>
      {chrome?.titleHost ? (
        createPortal(heading, chrome.titleHost)
      ) : (
        <div className="flex flex-wrap items-start justify-between gap-3">
          {heading}
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </div>
      )}
      {/* Portalled: the actions keep the page's first row to themselves, still on the end edge. */}
      {chrome?.titleHost && actions && (
        <div className="flex flex-wrap items-center justify-end gap-2">{actions}</div>
      )}
      {children}
    </div>
  );
}
