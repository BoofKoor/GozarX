import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "@/i18n";
import type { DashboardAnalytics } from "@/types/api";

import { ActivationPanel } from "./ActivationPanel";

const data = (median: number | null): DashboardAnalytics =>
  ({
    median_hours_to_claim: { value: median, previous: null, change_pct: null },
    activation_24h: { value: 74, previous: 71.2, change_pct: 3.9 },
    first_claimers_in_range: 1180,
  }) as DashboardAnalytics;

function show(median: number | null) {
  return render(
    <I18nProvider>
      <ActivationPanel data={data(median)} />
    </I18nProvider>,
  );
}

describe("ActivationPanel", () => {
  it("shows an em dash rather than a zero when a median cannot exist", () => {
    // An empty cohort has no median. Rendering it as 0 would claim instant activation — which is
    // the one thing that cannot be distinguished from the real figure, since the real figure on a
    // live install genuinely is a few seconds.
    show(null);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("keeps a sub-minute median legible instead of rounding it to zero", () => {
    // 0.0058 hours is the measured production value: 21 seconds, because the whole flow is
    // /start, pick a language, claim. Printed as hours it was "0" and read as a broken tile.
    show(0.0058);
    expect(screen.getByText("⁨۲۱s⁩")).toBeInTheDocument();
  });
});
