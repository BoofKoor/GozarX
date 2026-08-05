import { clsx } from "clsx";
import { type ReactNode, useRef } from "react";

import { useFocusTrap } from "./useFocusTrap";

/**
 * Accessible modal dialog: `role="dialog"` + `aria-modal`, Esc-to-close, focus moved in on open and
 * restored on close, Tab trapped inside, background scroll locked, and a backdrop click (mousedown,
 * so a drag that ends outside doesn't close) to dismiss. Replaces the hand-rolled `fixed inset-0`
 * overlays that had none of this (M7).
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

  return (
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
          "animate-scale-in w-full rounded-2xl border border-line bg-surface shadow-overlay outline-none",
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
}
