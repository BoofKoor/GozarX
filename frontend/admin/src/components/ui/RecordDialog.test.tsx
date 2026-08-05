import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/i18n";

import { RecordDialog } from "./RecordDialog";

function open(onClose = vi.fn(), extra?: React.ReactNode) {
  render(
    <I18nProvider>
      <RecordDialog open onClose={onClose} title="کارت کاربر" sub="5000000000">
        <button type="button">اقدام اول</button>
        {extra}
      </RecordDialog>
    </I18nProvider>,
  );
  return onClose;
}

describe("RecordDialog", () => {
  it("announces its own title, so the record is identifiable", () => {
    open();
    // role + aria-modal alone leaves a screen reader saying "dialog" and nothing else.
    expect(screen.getByRole("dialog", { name: "کارت کاربر" })).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const onClose = open();
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("moves focus into the dialog on open", () => {
    open();
    // The first focusable in DOM order is the header's close button — focus must be INSIDE the
    // dialog, not left behind on whatever opened it.
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "بستن" }));
  });

  it("keeps Tab inside the dialog", async () => {
    open();
    const first = screen.getByRole("button", { name: "اقدام اول" });
    const close = screen.getByRole("button", { name: "بستن" });
    // Two focusables: forward from the last must wrap to the first, not escape to the page.
    close.focus();
    await userEvent.tab();
    expect(document.activeElement).toBe(first);
  });

  it("renders nothing while closed", () => {
    render(
      <I18nProvider>
        <RecordDialog open={false} onClose={vi.fn()} title="x">
          body
        </RecordDialog>
      </I18nProvider>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
