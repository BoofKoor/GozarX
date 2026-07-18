/** True only if every value is a finite number ≥ its min. The economy forms call this on submit so a
 *  cleared (NaN) or out-of-range field can't be saved — the old forms coerced "" to 0 and wrote it
 *  straight to the runtime economy (M4). */
export function allValidNumbers(checks: { value: number; min: number }[]): boolean {
  return checks.every((c) => Number.isFinite(c.value) && c.value >= c.min);
}
