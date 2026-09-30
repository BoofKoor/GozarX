"use client";

import { type RefObject, useEffect, useRef } from "react";

// The behaviour every modal surface owes a keyboard (and screen-reader) user, in ONE place — the
// same contract the admin panel's `useFocusTrap` keeps (C-39):
//
//   Esc closes · focus moves in on open and goes back to whatever had it on close · Tab cycles
//   inside instead of escaping to the page behind · the page behind does not scroll.
//
// The phone menu, the rewards overlays and the reset confirmation each carried a partial copy of
// this (Esc here, a focus() there, a scroll lock nowhere), so Tab walked out of an open menu into
// the widget under it and the page scrolled behind every dialog.
//
// `onClose` is read through a ref: callers pass inline arrows, and an effect keyed on the callback
// would re-run on every render — re-capturing "what had focus before" as the dialog itself.

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Focusable descendants in DOM order, skipping hidden ones. Hidden-ness is read from ATTRIBUTES,
 *  not layout: `offsetParent` is null for every `position: fixed` element, which a dialog is. */
function focusable(container: HTMLElement | null): HTMLElement[] {
  if (!container) return [];
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => !el.closest("[hidden], [inert], [aria-hidden='true']"),
  );
}

export function useFocusTrap(
  panelRef: RefObject<HTMLElement | null>,
  onClose: () => void,
  open = true,
  /** where focus should land on open; the first focusable otherwise */
  initialFocus?: RefObject<HTMLElement | null>,
): void {
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const body = document.body;
    const prevOverflow = body.style.overflow;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        closeRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const panel = panelRef.current;
      const items = focusable(panel);
      if (items.length === 0) {
        e.preventDefault();
        panel?.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      // focus that somehow sits outside (or on the panel itself) re-enters at the right end
      if (!panel?.contains(active) || active === panel) {
        e.preventDefault();
        (e.shiftKey ? last : first).focus();
      } else if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKey);
    body.style.overflow = "hidden";
    const target = initialFocus?.current ?? focusable(panelRef.current)[0] ?? panelRef.current;
    target?.focus({ preventScroll: true });

    return () => {
      document.removeEventListener("keydown", onKey);
      body.style.overflow = prevOverflow;
      // only hand focus back if it is still inside the closing surface (or nowhere) — a click that
      // closed the menu by following a link has already put focus where the visitor went
      const active = document.activeElement;
      if (!active || active === document.body || panelRef.current?.contains(active)) {
        previouslyFocused?.focus?.({ preventScroll: true });
      }
    };
  }, [open, panelRef, initialFocus]);
}
