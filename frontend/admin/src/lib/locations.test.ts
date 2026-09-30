import { describe, expect, it } from "vitest";

import { normalizeRemark, resolveSelection } from "./locations";

describe("normalizeRemark", () => {
  it("folds the same differences the server folds", () => {
    expect(normalizeRemark("Germany {{TRAFFIC_LEFT}}")).toBe("germany");
    expect(normalizeRemark("  آلمان\u200cشرقی ")).toBe("آلمان شرقی");
    expect(normalizeRemark("ＤＥ")).toBe("de"); // full-width, NFKC
  });
});

describe("resolveSelection", () => {
  const live = ["Germany", "Finland", "Mexico"];

  it("drops a name the squad no longer serves, and reports it", () => {
    expect(resolveSelection(["Germany", "Old host"], live)).toEqual({
      save: ["Germany"],
      stale: ["Old host"],
      all: false,
    });
  });

  it("saves the squad's own spelling", () => {
    expect(resolveSelection(["germany "], live).save).toEqual(["Germany"]);
  });

  it("collapses a full selection to [] — all of them, live", () => {
    expect(resolveSelection(["Mexico", "Finland", "Germany"], live)).toEqual({
      save: [],
      stale: [],
      all: true,
    });
  });

  it("reads a selection of nothing but stale names as all, never as none", () => {
    expect(resolveSelection(["Gone", "Also gone"], live)).toEqual({
      save: [],
      stale: ["Gone", "Also gone"],
      all: true,
    });
  });
});
