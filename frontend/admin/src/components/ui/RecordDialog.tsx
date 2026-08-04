import { clsx } from "clsx";
import { X } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";

import { useI18n } from "@/i18n";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function focusable(container: HTMLElement | null): HTMLElement[] {
  if (!container) return [];
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el.offsetParent !== null,
  );
}

/**
 * Record detail — a centred dialog over a blurred backdrop.
 *
 * This replaces the side sheet it grew out of. A record is something you step INTO and back out of;
 * a panel pinned to one edge makes the reader hold two layouts at once, and on a narrow console it
 * is the whole screen anyway with a sliver of wasted context.
 *
 * Accessibility contract, unchanged from the sheet: Esc closes, focus moves in and is restored on
 * exit, Tab is trapped, background scroll is locked. The backdrop closes too — but only when the
 * backdrop ITSELF is the target, so a drag that starts inside the dialog and releases outside does
 * not throw the record away.
 */
export function RecordDialog({
  open,
  onClose,
  title,
  sub,
  children,
  footer,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  sub?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const { t } = useI18n();

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusable(panelRef.current);
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    (focusable(panelRef.current)[0] ?? panelRef.current)?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      previouslyFocused?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="animate-fade-in fixed inset-0 z-50 grid place-items-center bg-black/50 p-4 backdrop-blur-md sm:p-6"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        className={clsx(
          "animate-scale-in flex max-h-full w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-overlay outline-none",
          className,
        )}
      >
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-base font-bold text-content">{title}</h2>
            {sub && <p className="mt-0.5 truncate text-xs text-content-muted">{sub}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("ui.close")}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-content-subtle transition hover:bg-surface-hover hover:text-content"
          >
            <X className="h-5 w-5" />
          </button>
        </header>
        <div className="scrollbar-thin flex-1 overflow-y-auto p-5">{children}</div>
        {footer && (
          <footer className="flex items-center gap-2 border-t border-line px-5 py-3">
            {footer}
          </footer>
        )}
      </div>
    </div>
  );
}
