import { describe, expect, it } from "vitest";

import { ticksFor } from "./Overview";

// `AreaTrend` scales its plot to the TOP tick, so these two properties are what keep the tallest
// curve inside the frame and every gridline on a figure an operator can read. The chart used to
// scale to the data max instead, which put a ceiling of 400 above a peak of 356 clean off the
// canvas — the top gridline and its label simply were not drawn.
describe("ticksFor", () => {
  const MAXIMA = [1, 2, 7, 8, 13, 45, 99, 100, 137, 300, 356, 1024, 9999];

  it("puts the top strictly above the data, so the peak never touches the last line", () => {
    for (const max of MAXIMA) {
      const ticks = ticksFor(max);
      expect(ticks).toHaveLength(5);
      expect(ticks[4]).toBeGreaterThan(max);
    }
  });

  it("spaces five whole-number gridlines evenly from zero", () => {
    for (const max of MAXIMA) {
      const ticks = ticksFor(max);
      const step = ticks[1];
      expect(ticks[0]).toBe(0);
      expect(ticks).toEqual([0, step, step * 2, step * 3, step * 4]);
      for (const t of ticks) expect(Number.isInteger(t)).toBe(true);
    }
  });

  it("labels a 356-high chart in round hundreds, as the design does", () => {
    expect(ticksFor(356)).toEqual([0, 100, 200, 300, 400]);
  });

  it("still produces a usable scale with no data at all", () => {
    expect(ticksFor(0)).toEqual([0, 1, 2, 3, 4]);
  });
});
