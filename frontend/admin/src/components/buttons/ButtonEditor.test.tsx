import { render as rtlRender, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "@/components/ui/confirm";
import { useUpdateButton } from "@/hooks/useButtons";
import type { ButtonConfig } from "@/types/api";

import { ButtonEditor } from "./ButtonEditor";

vi.mock("@/hooks/useButtons", () => ({ useUpdateButton: vi.fn() }));

// The editor asks before discarding unsaved edits, which needs the app's confirm provider.
const render = (ui: ReactElement) => rtlRender(<ConfirmProvider>{ui}</ConfirmProvider>);

function btn(over: Partial<ButtonConfig>): ButtonConfig {
  return {
    key: "menu_config",
    screen: "main_menu",
    is_critical: false,
    is_visible: true,
    default_row: 0,
    default_position: 0,
    effective_row: 0,
    effective_position: 0,
    default_label: { fa: "پیش‌فرض", en: "Default", ru: "По" },
    effective_label: { fa: "پیش‌فرض", en: "Default", ru: "По" },
    style: null,
    customized: false,
    ...over,
  };
}

describe("ButtonEditor", () => {
  beforeEach(() => {
    vi.mocked(useUpdateButton).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateButton>);
  });

  it("locks the visibility toggle for critical buttons", () => {
    render(<ButtonEditor button={btn({ key: "back", is_critical: true })} onClose={() => {}} />);
    expect(screen.getByRole("button", { name: /نمایش داده می‌شود/ })).toBeDisabled();
    expect(screen.getByText(/دکمهٔ حیاتی/)).toBeInTheDocument();
  });

  it("allows toggling visibility for normal buttons", () => {
    render(<ButtonEditor button={btn({ is_critical: false })} onClose={() => {}} />);
    expect(screen.getByRole("button", { name: /نمایش داده می‌شود/ })).not.toBeDisabled();
    expect(screen.queryByText(/دکمهٔ حیاتی/)).not.toBeInTheDocument();
  });

  it("asks before Esc throws away an edited label, and closes at once when nothing changed", async () => {
    const onClose = vi.fn();
    const { unmount } = render(<ButtonEditor button={btn({})} onClose={onClose} />);
    // Untouched: Esc simply closes.
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
    unmount();

    const onClose2 = vi.fn();
    render(<ButtonEditor button={btn({})} onClose={onClose2} />);
    const [fa] = screen.getAllByRole("textbox");
    await userEvent.clear(fa);
    await userEvent.type(fa, "برچسب تازه");
    await userEvent.keyboard("{Escape}");
    // Edited: the confirm asks first, and "keep editing" keeps the dialog open.
    expect(onClose2).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "ادامهٔ ویرایش" }));
    expect(onClose2).not.toHaveBeenCalled();
    expect(fa).toHaveValue("برچسب تازه");
  });
});
