import { clsx } from "clsx";
import { type ReactNode, useRef } from "react";
import { createPortal } from "react-dom";

import { useFocusTrap } from "./useFocusTrap";

/**
 * Accessible modal dialog: `role="dialog"` + `aria-modal`, Esc-to-close, focus moved in on open and
 * restored on close, Tab trapped inside, background scroll locked, and a backdrop click (mousedown,
 * so a drag that ends outside doesn't close) to dismiss. Replaces the hand-rolled `fixed inset-0`
 * overlays that had none of this (M7).
 *
 * Rendered through a PORTAL to `<body>`. `fixed inset-0` means "the viewport" only until some
 * ancestor has a transform, a filter or containment — and the shell's own entry animation ends on
 * `transform: translateY(0)` with `animation-fill-mode: both`, so it keeps a computed
 * `matrix(1,0,0,1,0,0)` forever and quietly becomes the containing block for every fixed descendant.
 * A dialog opened from a page then centred itself inside the 1180px content column instead of the
 * window, its backdrop stopped at that column's edges, and `max-h-full` measured the column's full
 * scroll height, so it never scrolled internally and simply ran off the bottom of the screen.
 */
export function Modal({
  onClose,
  children,
  className,
  labelledBy,
}: {
  onClose: () => void;
  children: ReactNode;
  className?: string;
  labelledBy?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  useFocusTrap(panelRef, onClose);

  return createPortal(
    <div
      className="animate-fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onMouseDown={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
        className={clsx(
          "animate-scale-in max-h-full w-full overflow-y-auto rounded-2xl bg-surface shadow-overlay outline-none",
          className,
        )}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}
