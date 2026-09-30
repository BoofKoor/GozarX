import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { BOUNDS } from "./bounds";

/**
 * `BOUNDS` claims to mirror the server's `web/routes/admin/bounds.py`, and a mirror kept by hand
 * drifts: `streakDays` said `min: 1` where the server allows 0 ("off"), so a stored 0 failed the
 * form's own check and the whole site settings page could not be saved. This reads the server's
 * file, so the two can only disagree in a failing test.
 */
const SERVER_FILE = join(
  __dirname,
  "..",
  "..",
  "..",
  "..",
  "backend",
  "gozar",
  "web",
  "routes",
  "admin",
  "bounds.py",
);

/** The server's alias for each client range. */
const SERVER_NAME: Record<keyof typeof BOUNDS, string> = {
  trialHours: "TrialHours",
  dailyLimitMb: "DailyLimitMb",
  rewardMb: "RewardMb",
  rewardLimit: "RewardLimit",
  configsPerPage: "ConfigsPerPage",
  streakDays: "StreakDays",
};

/** The file's bound expressions: integers (`100_000`), products of them, and `_MB_PER_TB`. */
function evaluate(expr: string): number {
  return expr
    .split("*")
    .map((part) => part.trim())
    .map((part) => (part === "_MB_PER_TB" ? 1024 * 1024 : Number(part.replace(/_/g, ""))))
    .reduce((a, b) => a * b, 1);
}

describe("BOUNDS", () => {
  it("holds to the server's ranges, field for field", () => {
    const py = readFileSync(SERVER_FILE, "utf8");
    for (const [key, name] of Object.entries(SERVER_NAME)) {
      const match = py.match(
        new RegExp(`^${name} = Annotated\\[int, Field\\(ge=([^,]+), le=([^)]+)\\)\\]`, "m"),
      );
      expect(match, `${name} not found in bounds.py`).not.toBeNull();
      const [, ge, le] = match!;
      expect(BOUNDS[key as keyof typeof BOUNDS], name).toEqual({
        min: evaluate(ge),
        max: evaluate(le),
      });
    }
  });
});
