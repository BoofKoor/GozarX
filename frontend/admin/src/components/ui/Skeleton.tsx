import { clsx } from "clsx";

/** Animated placeholder block — fills layout while data loads so the page doesn't jump. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        "relative overflow-hidden rounded-lg bg-surface-sunken",
        // Sheen sweep on top of the block; `animate-shimmer` runs right → left to match RTL reading.
        "after:absolute after:inset-0 after:animate-shimmer after:bg-gradient-to-l",
        "after:from-transparent after:via-white/25 after:to-transparent dark:after:via-white/[0.06]",
        className,
      )}
      aria-hidden
    />
  );
}
