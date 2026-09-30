import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LocationPicker } from "./LocationPicker";

const AVAILABLE = ["Germany", "Finland", "Netherlands"];

function setup(overrides: Partial<Parameters<typeof LocationPicker>[0]> = {}) {
  const onChange = vi.fn();
  render(
    <LocationPicker
      available={AVAILABLE}
      selected={[]}
      onChange={onChange}
      fallbackText=""
      onFallbackTextChange={() => {}}
      {...overrides}
    />,
  );
  return { onChange };
}

describe("LocationPicker", () => {
  it("treats an empty selection as 'all of them'", () => {
    setup();
    for (const name of AVAILABLE) {
      expect(screen.getByLabelText(name)).toBeChecked();
    }
  });

  it("starts from the full list when the first box is unticked", async () => {
    const { onChange } = setup();
    await userEvent.click(screen.getByLabelText("Finland"));
    // An empty selection means "all" on the backend, so unticking one has to send the REST of the
    // list — not an empty array, and not a single-entry one.
    expect(onChange).toHaveBeenCalledWith(["Germany", "Netherlands"]);
  });

  it("removes only the unticked entry from an explicit selection", async () => {
    const { onChange } = setup({ selected: ["Germany", "Finland"] });
    await userEvent.click(screen.getByLabelText("Germany"));
    expect(onChange).toHaveBeenCalledWith(["Finland"]);
  });

  it("falls back to a text box, with a warning, when the panel can't be reached", () => {
    setup({ available: undefined, unavailable: true, fallbackText: "آلمان" });
    expect(screen.queryByLabelText("Germany")).not.toBeInTheDocument();
    expect(screen.getByDisplayValue("آلمان")).toBeInTheDocument();
    expect(screen.getByText(/از پنل گرفته نشد/)).toBeInTheDocument();
  });

  it("names a saved location the squad dropped, and never sends it", async () => {
    // The reported bug: stored names the squad stopped serving stayed in the selection with no
    // checkbox to show them, so ticking a NEW location read "29 of 25" and the save came back 400.
    const { onChange } = setup({
      available: [...AVAILABLE, "Mexico"],
      selected: ["Germany", "Finland", "Netherlands", "{{STATUS}} | GozarX", "🇩🇪 DE"],
    });
    expect(screen.getByRole("status")).toHaveTextContent("{{STATUS}} | GozarX، 🇩🇪 DE");
    expect(screen.getByText("۳ از ۴ انتخاب شده")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Mexico"));
    // Everything ticked collapses to [] — "all of them", so a host added later appears by itself.
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("matches a saved name the way the server does, not verbatim", () => {
    setup({ selected: ["germany ", "Finland"] });
    expect(screen.getByLabelText("Germany")).toBeChecked();
    expect(screen.getByLabelText("Netherlands")).not.toBeChecked();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("keeps the last ticked location instead of saving 'none', which means all", async () => {
    const { onChange } = setup({ selected: ["Germany"] });
    await userEvent.click(screen.getByLabelText("Germany"));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("says a squad with no host has nothing to pick, instead of offering a box it would ignore", () => {
    setup({ available: [] });
    expect(screen.getByText(/هیچ host فعالی ندارد/)).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
