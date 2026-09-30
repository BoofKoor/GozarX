import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * TABBABLE descendants, in DOM order, skipping anything explicitly hidden.
 *
 * Hiddenness is read from ATTRIBUTES rather than from `offsetParent`. Layout is the tempting
 * signal, but `offsetParent` is null for any `position: fixed` element — which every dialog panel
 * here is — and it is null for everything under jsdom, where it silently emptied this list and
 * made the whole trap untestable.
 *
 * A native control taken out of the tab order (`tabIndex={-1}`) is skipped too: the selector
 * matches every `button`, so the command palette's options — deliberately untabbable, focus lives
 * in its input — became the trap's "last" element. Tab was then never caught at the end and walked
 * out of the dialog, and Shift+Tab from the input focused the last option, where Enter ran it.
 */
function focusable(container: HTMLElement | null): HTMLElement[] {
  if (!container) return [];
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) =>
      el.tabIndex >= 0 && !el.closest("[hidden]") && el.getAttribute("aria-hidden") !== "true",
  );
}

/** Open traps, innermost last. Only the top one answers the keyboard, and the page's scroll lock
 *  holds until the LAST one closes. */
const stack: symbol[] = [];

/**
 * The behaviour every modal surface owes a keyboard user, in one place.
 *
 * Esc closes · focus moves in on open and is restored to whatever had it on close · Tab cycles
 * inside instead of escaping to the page behind · background scroll is locked.
 *
 * `Modal` and `RecordDialog` each carried their own copy of this — the same thirty lines twice,
 * which is two places for the contract to drift apart.
 *
 * Two things it used to get wrong:
 *
 * - `onClose` is read through a ref. As an effect dependency, the inline `() => setX(null)` every
 *   caller passes is a new function each render, so any parent re-render tore the trap down and
 *   rebuilt it — dropping focus back on the first button. After "allow another claim" the list
 *   refetched, focus landed on «بستن», and the next Enter closed the dialog; in the quick search
 *   the same happened on every keystroke.
 * - Stacked dialogs (a confirm over a record) each listened for Esc, so one Esc closed both, and
 *   the inner one's cleanup released the page's scroll lock with the outer one still open.
 */
export function useFocusTrap(
  panelRef: RefObject<HTMLElement | null>,
  onClose: () => void,
  open = true,
): void {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const id = Symbol("focus-trap");
    stack.push(id);
    const isTop = () => stack[stack.length - 1] === id;
    const previouslyFocused = document.activeElement as HTMLElement | null;

    const onKey = (e: KeyboardEvent) => {
      if (!isTop()) return; // a dialog stacked above this one owns the keyboard
      if (e.key === "Escape") {
        closeRef.current();
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
      const at = stack.indexOf(id);
      if (at >= 0) stack.splice(at, 1);
      if (stack.length === 0) document.body.style.overflow = "";
      previouslyFocused?.focus?.();
    };
  }, [panelRef, open]);
}
