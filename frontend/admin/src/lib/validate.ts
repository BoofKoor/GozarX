/** True only if every value is a finite number within its bounds. The economy forms call this on
 *  submit so a cleared (NaN) or out-of-range field can't be saved — the old forms coerced "" to 0
 *  and wrote it straight to the runtime economy (M4), and nothing stopped a value above any sane
 *  ceiling (the server now refuses those too; see `lib/bounds`). */
export function allValidNumbers(checks: { value: number; min: number; max?: number }[]): boolean {
  return checks.every(
    (c) =>
      Number.isFinite(c.value) && c.value >= c.min && (c.max === undefined || c.value <= c.max),
  );
}
