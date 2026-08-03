import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RetentionCohorts } from "./RetentionCohorts";

describe("RetentionCohorts", () => {
  it("renders a cell per cohort week and leaves younger cohorts blank", () => {
    render(
      <RetentionCohorts
        data={{
          weeks: 4,
          cohorts: [
            { week: "2026-07-06", size: 10, retention: [100, 50, 20] },
            { week: "2026-07-27", size: 4, retention: [75] }, // this week's cohort, only 1 column
          ],
        }}
      />,
    );
    // A cohort younger than N weeks must show NOTHING for the missing columns — painting a 0%
    // there would read as "nobody came back" instead of "no data yet".
    const cells = screen.getAllByTitle(/از/);
    expect(cells).toHaveLength(4); // 3 + 1
  });

  it("shows an empty state instead of a bare table when there are no cohorts", () => {
    render(<RetentionCohorts data={{ weeks: 8, cohorts: [] }} />);
    expect(screen.getByText("هنوز کوهورتی نیست")).toBeInTheDocument();
  });
});
