import { describe, expect, it } from "vitest";

import { areaFrom, rosePath, rosePoints, smoothPath, spokeAngles, type Point } from "./geometry";

describe("smoothPath", () => {
  it("starts on the first point and ends on the last", () => {
    const pts: Point[] = [
      [0, 10],
      [10, 0],
      [20, 6],
    ];
    const d = smoothPath(pts);
    expect(d.startsWith("M0.00,10.00")).toBe(true);
    expect(d.endsWith("20.00,6.00")).toBe(true);
  });

  it("survives degenerate input instead of emitting NaN", () => {
    expect(smoothPath([])).toBe("");
    expect(smoothPath([[3, 4]])).toBe("M3,4");
    expect(smoothPath([[0, 0]] as Point[])).not.toContain("NaN");
  });
});

describe("areaFrom", () => {
  it("closes the line down to the baseline and back", () => {
    const pts: Point[] = [
      [0, 5],
      [10, 2],
    ];
    expect(areaFrom(smoothPath(pts), pts, 40)).toContain("L10.00,40L0.00,40Z");
  });
});

describe("rosePoints", () => {
  const angles = spokeAngles(4);

  it("interleaves a waist between every pair of data vertices", () => {
    const pts = rosePoints(angles, [80, 60, 70, 40]);
    expect(pts).toHaveLength(8);
    expect(pts.filter((_, i) => i % 2 === 0).map((p) => p.r)).toEqual([80, 60, 70, 40]);
  });

  it("puts every waist strictly below BOTH of its neighbours", () => {
    // This is the property the whole construction rests on: the tangential handles are only the
    // correct direction if each point is a radial extremum. A waist that outgrew a neighbour would
    // make the curve bulge where it should pinch.
    const radii = [79.1, 58, 68.1, 37.7];
    const pts = rosePoints(angles, radii);
    for (let i = 0; i < 4; i++) {
      const waist = pts[i * 2 + 1].r;
      expect(waist).toBeLessThan(radii[i]);
      expect(waist).toBeLessThan(radii[(i + 1) % 4]);
    }
  });

  it("scales the indentation with the multiplier, not with a fixed inset", () => {
    const shallow = rosePoints(angles, [80, 60, 70, 40], 1.1)[1].r;
    const deep = rosePoints(angles, [80, 60, 70, 40], 0.9)[1].r;
    expect(shallow).toBeGreaterThan(deep);
  });

  it("does not divide by zero when both neighbours are zero", () => {
    const pts = rosePoints(angles, [0, 0, 0, 0]);
    expect(pts.every((p) => Number.isFinite(p.r))).toBe(true);
  });
});

describe("rosePath", () => {
  it("closes the curve and emits only finite coordinates", () => {
    const d = rosePath(100, 100, rosePoints(spokeAngles(4), [80, 60, 70, 40]));
    expect(d.endsWith("Z")).toBe(true);
    expect(d).not.toContain("NaN");
  });

  it("is empty for no points rather than emitting a bare M", () => {
    expect(rosePath(0, 0, [])).toBe("");
  });
});

describe("spokeAngles", () => {
  it("starts at twelve o'clock and runs clockwise in screen space", () => {
    const [top, right] = spokeAngles(4);
    expect(Math.cos(top)).toBeCloseTo(0);
    expect(Math.sin(top)).toBeCloseTo(-1); // y grows downward, so -1 is up
    expect(Math.cos(right)).toBeCloseTo(1);
  });
});
