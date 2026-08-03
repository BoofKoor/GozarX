import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Field } from "./Field";
import { Input } from "./Input";

describe("Field", () => {
  it("associates the label with its control", () => {
    render(
      <Field label="حجم روزانه">
        <Input />
      </Field>,
    );
    // getByLabelText only resolves when label/for and input/id are wired — the thing the four
    // hand-copied `Labeled` helpers never did.
    expect(screen.getByLabelText("حجم روزانه")).toBeInTheDocument();
  });

  it("exposes an error through aria and hides the hint while it shows", () => {
    render(
      <Field label="لینک" hint="با https:// شروع کنید" error="نشانی نامعتبر است">
        <Input />
      </Field>,
    );
    const input = screen.getByLabelText("لینک");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("نشانی نامعتبر است");
    expect(screen.queryByText("با https:// شروع کنید")).not.toBeInTheDocument();
    // The control points at the error node, so a screen reader announces it on focus.
    expect(input.getAttribute("aria-describedby")).toBe(screen.getByRole("alert").id);
  });

  it("leaves a control usable outside a Field", () => {
    render(<Input aria-label="آزاد" />);
    const input = screen.getByLabelText("آزاد");
    expect(input).not.toHaveAttribute("aria-invalid");
  });
});
