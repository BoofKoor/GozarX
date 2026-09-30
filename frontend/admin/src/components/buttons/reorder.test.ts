import { describe, expect, it } from "vitest";

import { planReorder, type RowLayout } from "./reorder";

const pos = (items: { key: string; row_index: number; position: number }[] | null) =>
  Object.fromEntries((items ?? []).map((i) => [i.key, [i.row_index, i.position]]));

/** The screen after a reorder lands: the items regrouped into rows, the way the editor reads them. */
function landed(items: { key: string; row_index: number; position: number }[]): RowLayout[] {
  const byRow = new Map<number, { key: string; position: number }[]>();
  for (const i of items) byRow.set(i.row_index, [...(byRow.get(i.row_index) ?? []), i]);
  return [...byRow.entries()]
    .sort(([a], [b]) => a - b)
    .map(([row, keys]) => ({
      row,
      keys: keys.sort((a, b) => a.position - b.position).map((k) => k.key),
    }));
}

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
    const out = pos(planReorder(rows, "increase_traffic", "newrow", new Set(["back"])));
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

  it("keeps row numbers dense, so repeated moves never walk up to the server's cap", () => {
    // Kept verbatim, "new row" was max + 1 on every move: the 98th asked for row 100 (cap: 99).
    let rows: RowLayout[] = [
      { row: 0, keys: ["a"] },
      { row: 1, keys: ["b"] },
      { row: 2, keys: ["c"] },
    ];
    for (let move = 0; move < 200; move++)
      rows = landed(planReorder(rows, rows[0].keys[0], "newrow")!);
    expect(rows.map((r) => r.row)).toEqual([0, 1, 2]);
  });

  it("numbers around a locked row without ever moving it", () => {
    const locked = new Set(["back"]);
    let rows: RowLayout[] = [
      { row: 0, keys: ["a"] },
      { row: 1, keys: ["b"] },
      { row: 4, keys: ["back"] },
    ];
    for (let move = 0; move < 50; move++) {
      const top = rows.find((r) => !r.keys.includes("back"))!.keys[0];
      rows = landed(planReorder(rows, top, "newrow", locked)!);
      const back = rows.find((r) => r.keys.includes("back"))!;
      expect(back.row).toBe(4); // the server pins it there, so the plan must agree
      expect(back.keys).toEqual(["back"]); // and nothing is numbered into its row
    }
    expect(Math.max(...rows.map((r) => r.row))).toBeLessThanOrEqual(6);
  });

  it("is a no-op for a drop onto itself", () => {
    expect(planReorder([{ row: 0, keys: ["a", "b"] }], "a", "a")).toBeNull();
  });
});
