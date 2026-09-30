/**
 * The economy numbers' valid ranges — the mirror of the server's `web/routes/admin/bounds.py`,
 * which refuses anything outside them with a 422. The forms hold to the same numbers so a value
 * is refused where it is typed, in the operator's language, instead of by a server error.
 */
export const BOUNDS = {
  trialHours: { min: 1, max: 24 * 365 },
  /** From 1: Remnawave reads a traffic limit of 0 as UNLIMITED. */
  dailyLimitMb: { min: 1, max: 1024 * 1024 },
  rewardMb: { min: 0, max: 1024 * 1024 },
  /** 0 rewards no invite at all — the quota is min(referrals, cap). */
  rewardLimit: { min: 0, max: 100_000 },
  configsPerPage: { min: 1, max: 50 },
  /** From 0: 0 switches the streak bonus off. From 1, a stored 0 failed the form's own check, and
   *  the whole site settings page could not be saved. */
  streakDays: { min: 0, max: 365 },
} as const;
