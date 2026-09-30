import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/i18n";

import { HourStrip } from "./HourStrip";

const COUNTS = Array.from({ length: 24 }, (_, h) => (h === 21 ? 100 : 1));

describe("HourStrip", () => {
  it("is one tab stop — the chosen hour — not twenty-four", () => {
    render(
      <I18nProvider>
        <HourStrip counts={COUNTS} mark={21} onPick={() => {}} />
      </I18nProvider>,
    );
    const hours = screen.getAllByRole("radio");
    expect(hours).toHaveLength(24);
    expect(hours.filter((h) => h.tabIndex === 0)).toEqual([hours[21]]);
    expect(hours[21]).toHaveAttribute("aria-checked", "true");
  });

  it("walks the clock with the arrows, left to right in either language", async () => {
    const onPick = vi.fn();
    render(
      <I18nProvider>
        <HourStrip counts={COUNTS} mark={21} onPick={onPick} />
      </I18nProvider>,
    );
    screen.getAllByRole("radio")[21].focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(onPick).toHaveBeenLastCalledWith(22);
    await userEvent.keyboard("{Home}");
    expect(onPick).toHaveBeenLastCalledWith(0);
  });

  it("keeps a radio group's keys: Down is later, Up is earlier, and the clock wraps", async () => {
    const picks: number[] = [];
    const { rerender } = render(
      <I18nProvider>
        <HourStrip counts={COUNTS} mark={21} onPick={(h) => picks.push(h)} />
      </I18nProvider>,
    );
    screen.getAllByRole("radio")[21].focus();
    await userEvent.keyboard("{ArrowDown}");
    await userEvent.keyboard("{ArrowUp}");
    rerender(
      <I18nProvider>
        <HourStrip counts={COUNTS} mark={23} onPick={(h) => picks.push(h)} />
      </I18nProvider>,
    );
    await userEvent.keyboard("{ArrowRight}");
    expect(picks).toEqual([22, 20, 0]);
  });

  it("stays out of the tab order as a read-only chart", () => {
    render(
      <I18nProvider>
        <HourStrip counts={COUNTS} mark={21} />
      </I18nProvider>,
    );
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
  });
});
