import { describe, expect, it } from "vitest";

import { nextZonedHour, zoneOffsetMinutes } from "./time";

describe("nextZonedHour", () => {
  it("is +03:30 for Tehran", () => {
    expect(zoneOffsetMinutes(new Date("2026-09-30T12:00:00Z"))).toBe(210);
  });

  it("builds the instant on the TEHRAN clock, whatever the browser's zone", () => {
    // 12:00 UTC is 15:30 in Tehran, so 21:00 Tehran is still ahead today: 17:30 UTC.
    const at = nextZonedHour(21, new Date("2026-09-30T12:00:00Z"));
    expect(at.toISOString()).toBe("2026-09-30T17:30:00.000Z");
  });

  it("rolls to tomorrow once the hour has passed in Tehran", () => {
    // 19:00 UTC is 22:30 in Tehran: 21:00 has gone, so it is tomorrow's.
    const at = nextZonedHour(21, new Date("2026-09-30T19:00:00Z"));
    expect(at.toISOString()).toBe("2026-10-01T17:30:00.000Z");
  });

  it("uses the Tehran DATE, not the UTC one, just after Tehran midnight", () => {
    // 21:00 UTC on the 30th is 00:30 on the 1st in Tehran; 08:00 Tehran on the 1st is 04:30 UTC.
    const at = nextZonedHour(8, new Date("2026-09-30T21:00:00Z"));
    expect(at.toISOString()).toBe("2026-10-01T04:30:00.000Z");
  });
});
