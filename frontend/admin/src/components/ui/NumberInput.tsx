import { forwardRef, type InputHTMLAttributes } from "react";

import { Input } from "./Input";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type"> & {
  value: number;
  onChange: (n: number) => void;
};

/**
 * Numeric input that represents a CLEARED field as `NaN` and renders it empty — instead of the old
 * `Number("") === 0`, which snapped a cleared field to 0 (so it couldn't be retyped) and let 0 be
 * saved over economy values like trial_hours/daily_limit (M4). Submit handlers validate with
 * `allValidNumbers` and reject NaN/out-of-range before mutating.
 */
export const NumberInput = forwardRef<HTMLInputElement, Props>(function NumberInput(
  { value, onChange, ...rest },
  ref,
) {
  return (
    <Input
      ref={ref}
      type="number"
      inputMode="numeric"
      value={Number.isNaN(value) ? "" : value}
      onChange={(e) => onChange(e.target.value === "" ? NaN : Number(e.target.value))}
      {...rest}
    />
  );
});
