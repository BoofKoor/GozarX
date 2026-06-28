import { clsx } from "clsx";
import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

const TONES: Record<BadgeTone, string> = {
  neutral: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  brand: "bg-brand/10 text-brand-700 dark:text-brand-200",
  success: "bg-success-50 text-success-700 dark:bg-success/15 dark:text-success-500",
  warning: "bg-warning-50 text-warning-700 dark:bg-warning/15 dark:text-warning-500",
  danger: "bg-danger-50 text-danger-700 dark:bg-danger/15 dark:text-danger-500",
  info: "bg-info-50 text-info-700 dark:bg-info/15 dark:text-info-500",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: BadgeTone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
