import { clsx } from "clsx";
import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

// Alpha-tinted fills read correctly on both the white and near-black surfaces, and the `*-700`
// "ink" shades flip per theme in tokens.css — so a tone needs ONE definition rather than a light
// class plus a `dark:` twin.
const TONES: Record<BadgeTone, string> = {
  neutral: "bg-surface-sunken text-content-muted",
  brand: "bg-brand/15 text-brand-700",
  success: "bg-success-500/15 text-success-700",
  warning: "bg-warning-500/15 text-warning-700",
  danger: "bg-danger-500/15 text-danger-700",
  info: "bg-info-500/15 text-info-700",
};

const DOTS: Record<BadgeTone, string> = {
  neutral: "bg-content-subtle",
  brand: "bg-brand",
  success: "bg-success-500",
  warning: "bg-warning-500",
  danger: "bg-danger-500",
  info: "bg-info-500",
};

export function Badge({
  tone = "neutral",
  dot = false,
  className,
  children,
}: {
  tone?: BadgeTone;
  /** Show a leading status dot — for live/state badges rather than plain counters. */
  dot?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
    >
      {dot && <span className={clsx("h-1.5 w-1.5 rounded-full", DOTS[tone])} aria-hidden />}
      {children}
    </span>
  );
}
