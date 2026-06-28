import { clsx } from "clsx";

/** Animated placeholder block — fills layout while data loads so the page doesn't jump. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={clsx("animate-pulse rounded-md bg-slate-200/70 dark:bg-slate-800", className)}
    />
  );
}
