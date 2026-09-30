import { describe, expect, it } from "vitest";

import { planReorder } from "./reorder";

const pos = (items: { key: string; row_index: number; position: number }[] | null) =>
  Object.fromEntries((items ?? []).map((i) => [i.key, [i.row_index, i.position]]));

describe("planReorder", () => {
  it("lands a forward move AFTER the button it was dropped on", () => {
    const out = planReorder([{ row: 0, keys: ["a", "b", "c"] }], "a", "c");
    expect(pos(out)).toEqual({ b: [0, 0], c: [0, 1], a: [0, 2] });
  });

  it("lands a backward move before it", () => {
    const out = planReorder([{ row: 0, keys: ["a", "b", "c"] }], "c", "a");
    expect(pos(out)).toEqual({ c: [0, 0], a: [0, 1], b: [0, 2] });
  });

  it("keeps real row numbers, so a moved button never shares the locked back row", () => {
    // landing: [get_config], [increase_traffic], [back (locked, stays on row 2 server-side)].
    const rows = [
      { row: 0, keys: ["get_config"] },
      { row: 1, keys: ["increase_traffic"] },
      { row: 2, keys: ["back"] },
    ];
    const out = pos(planReorder(rows, "increase_traffic", "newrow"));
    // Renumbered from zero, increase_traffic went to row 2 — back's row — and merged into it.
    expect(out.increase_traffic[0]).toBe(3);
    expect(out.back).toEqual([2, 0]);
  });

  it("does not count upward when a lone last-row button is dropped on 'new row' again", () => {
    const rows = [
      { row: 0, keys: ["a"] },
      { row: 1, keys: ["b"] },
    ];
    expect(pos(planReorder(rows, "b", "newrow")).b).toEqual([1, 0]);
  });

  it("is a no-op for a drop onto itself", () => {
    expect(planReorder([{ row: 0, keys: ["a", "b"] }], "a", "a")).toBeNull();
  });
});
