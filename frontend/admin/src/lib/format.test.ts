import { describe, expect, it } from "vitest";

import { formatMb, formatNumber, shortDay, splitLocations } from "./format";

describe("format helpers", () => {
  it("formats MB into GB when large", () => {
    expect(formatMb(512)).toBe("512 MB");
    expect(formatMb(1024)).toBe("1 GB");
    expect(formatMb(1536)).toBe("1.5 GB");
  });

  it("groups digits", () => {
    expect(formatNumber(12345)).toBe("12,345");
  });

  it("shortens an ISO day", () => {
    expect(shortDay("2026-06-27")).toBe("06/27");
  });

  it("splits locations on ASCII or Persian comma, trimming blanks", () => {
    expect(splitLocations("آلمان، هلند ,  , فرانسه")).toEqual(["آلمان", "هلند", "فرانسه"]);
    expect(splitLocations("")).toEqual([]);
  });
});
