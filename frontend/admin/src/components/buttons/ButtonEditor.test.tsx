import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useUpdateButton } from "@/hooks/useButtons";
import type { ButtonConfig } from "@/types/api";

import { ButtonEditor } from "./ButtonEditor";

vi.mock("@/hooks/useButtons", () => ({ useUpdateButton: vi.fn() }));

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
});
