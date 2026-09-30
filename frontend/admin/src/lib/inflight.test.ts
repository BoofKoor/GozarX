import { describe, expect, it } from "vitest";

import { stillInFlight } from "./inflight";

describe("stillInFlight", () => {
  const now = Date.parse("2026-09-30T12:00:00Z");

  it("polls a row that is queued or sending within the job's ceiling", () => {
    expect(stillInFlight([{ status: "sending", created_at: "2026-09-30T11:00:00Z" }], now)).toBe(
      true,
    );
  });

  it("stops polling a row older than any job can run — it is stuck, not busy", () => {
    expect(stillInFlight([{ status: "queued", created_at: "2026-09-29T12:00:00Z" }], now)).toBe(
      false,
    );
  });

  it("does not poll finished rows", () => {
    expect(stillInFlight([{ status: "done", created_at: "2026-09-30T11:59:00Z" }], now)).toBe(
      false,
    );
  });
});
