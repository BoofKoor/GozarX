import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ButtonConfig } from "@/types/api";

import { TelegramPreview } from "./TelegramPreview";

function btn(over: Partial<ButtonConfig>): ButtonConfig {
  return {
    key: "k",
    screen: "main_menu",
    is_critical: false,
    is_visible: true,
    default_row: 0,
    default_position: 0,
    effective_row: 0,
    effective_position: 0,
    default_label: { fa: "f", en: "e", ru: "r" },
    effective_label: { fa: "f", en: "e", ru: "r" },
    customized: false,
    ...over,
  };
}

describe("TelegramPreview", () => {
  it("renders visible buttons and drops hidden ones", () => {
    render(
      <TelegramPreview
        lang="fa"
        buttons={[
          btn({ key: "a", effective_label: { fa: "الف", en: "A", ru: "А" } }),
          btn({ key: "b", effective_row: 1, effective_label: { fa: "ب", en: "B", ru: "Б" } }),
          btn({ key: "c", is_visible: false, effective_label: { fa: "ج", en: "C", ru: "В" } }),
        ]}
      />,
    );
    expect(screen.getByText("الف")).toBeInTheDocument();
    expect(screen.getByText("ب")).toBeInTheDocument();
    expect(screen.queryByText("ج")).not.toBeInTheDocument();
  });

  it("shows an empty state when nothing is visible", () => {
    render(<TelegramPreview lang="fa" buttons={[btn({ is_visible: false })]} />);
    expect(screen.getByText("دکمه‌ای برای نمایش نیست")).toBeInTheDocument();
  });
});
