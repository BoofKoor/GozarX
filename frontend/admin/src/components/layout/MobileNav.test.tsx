import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/i18n";

import { MobileNav } from "./Sidebar";

function shellOf(el: HTMLElement): HTMLElement {
  // The drawer's outermost wrapper — the element that owns inert/aria-hidden.
  return el.closest("div.fixed") as HTMLElement;
}

function mount(open: boolean) {
  render(
    <MemoryRouter>
      <I18nProvider>
        <MobileNav open={open} onClose={vi.fn()} />
      </I18nProvider>
    </MemoryRouter>,
  );
  return shellOf(screen.getByRole("dialog", { hidden: true }));
}

describe("MobileNav", () => {
  it("is inert while closed, so its links stay out of the tab order", () => {
    // The drawer stays mounted to animate. `pointer-events-none` stops only the mouse — without
    // `inert`, Tab walked through every hidden nav link before reaching the page.
    const shell = mount(false);
    expect(shell).toHaveAttribute("inert");
    expect(shell).toHaveAttribute("aria-hidden", "true");
  });

  it("becomes reachable once opened", () => {
    const shell = mount(true);
    expect(shell).not.toHaveAttribute("inert");
    expect(shell).toHaveAttribute("aria-hidden", "false");
  });
});
