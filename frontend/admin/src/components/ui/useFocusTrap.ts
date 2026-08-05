import { useEffect, type RefObject } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Focusable descendants, in DOM order, skipping anything explicitly hidden.
 *
 * Hiddenness is read from ATTRIBUTES rather than from `offsetParent`. Layout is the tempting
 * signal, but `offsetParent` is null for any `position: fixed` element — which every dialog panel
 * here is — and it is null for everything under jsdom, where it silently emptied this list and
 * made the whole trap untestable.
 */
function focusable(container: HTMLElement | null): HTMLElement[] {
  if (!container) return [];
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => !el.closest("[hidden]") && el.getAttribute("aria-hidden") !== "true",
  );
}

/**
 * The behaviour every modal surface owes a keyboard user, in one place.
 *
 * Esc closes · focus moves in on open and is restored to whatever had it on close · Tab cycles
 * inside instead of escaping to the page behind · background scroll is locked.
 *
 * `Modal` and `RecordDialog` each carried their own copy of this — the same thirty lines twice,
 * which is two places for the contract to drift apart.
 */
export function useFocusTrap(
  panelRef: RefObject<HTMLElement | null>,
  onClose: () => void,
  open = true,
): void {
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
    // Move focus into the dialog (first focusable, else the panel itself).
    (focusable(panelRef.current)[0] ?? panelRef.current)?.focus();

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      previouslyFocused?.focus?.();
    };
  }, [panelRef, onClose, open]);
}
