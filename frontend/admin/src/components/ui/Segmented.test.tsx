import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Segmented } from "./Segmented";

const RANGES = [
  { value: 7, label: "۷ روز" },
  { value: 14, label: "۱۴ روز" },
  { value: 30, label: "۳۰ روز" },
];

describe("Segmented", () => {
  it("marks only the selected option as checked", () => {
    render(<Segmented value={14} onChange={() => {}} options={RANGES} ariaLabel="بازه" />);
    expect(screen.getByRole("radio", { name: "۱۴ روز" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "۷ روز" })).not.toBeChecked();
  });

  it("reports the picked value", async () => {
    const onChange = vi.fn();
    render(<Segmented value={7} onChange={onChange} options={RANGES} ariaLabel="بازه" />);
    await userEvent.click(screen.getByRole("radio", { name: "۳۰ روز" }));
    expect(onChange).toHaveBeenCalledWith(30);
  });

  it("is ONE tab stop, and the arrows step through it with the reading direction", async () => {
    // RTL (the test page's default is LTR, so the group sets it): the NEXT option is to the left.
    const onChange = vi.fn();
    render(
      <div dir="rtl">
        <Segmented value={7} onChange={onChange} options={RANGES} ariaLabel="بازه" />
      </div>,
    );
    const radios = screen.getAllByRole("radio");
    expect(radios.map((r) => r.tabIndex)).toEqual([0, -1, -1]);
    radios[0].focus();
    await userEvent.keyboard("{ArrowLeft}");
    expect(onChange).toHaveBeenLastCalledWith(14);
    await userEvent.keyboard("{End}");
    expect(onChange).toHaveBeenLastCalledWith(30);
  });
});
