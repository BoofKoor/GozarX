import { clsx } from "clsx";
import type { LucideIcon } from "lucide-react";

import { Card } from "@/components/ui/Card";

type Tone = "brand" | "success" | "info" | "warning" | "danger" | "neutral";

const TONE_CHIP: Record<Tone, string> = {
  brand: "bg-brand/10 text-brand",
  success: "bg-success-50 text-success-600 dark:bg-success/15 dark:text-success-500",
  info: "bg-info-50 text-info-600 dark:bg-info/15 dark:text-info-500",
  warning: "bg-warning-50 text-warning-600 dark:bg-warning/15 dark:text-warning-500",
  danger: "bg-danger-50 text-danger-600 dark:bg-danger/15 dark:text-danger-500",
  neutral: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400",
};

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "brand",
  hint,
  pulse,
}: {
  label: string;
  value: string | number;
  icon: LucideIcon;
  tone?: Tone;
  hint?: string;
  /** Show a live "ping" dot on the icon — used for the online-now KPI. */
  pulse?: boolean;
}) {
  return (
    <Card className="flex items-center gap-4 animate-fade-in">
      <div
        className={clsx(
          "relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl",
          TONE_CHIP[tone],
        )}
      >
        <Icon className="h-6 w-6" />
        {pulse && (
          <span className="absolute -left-0.5 -top-0.5 flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-success" />
          </span>
        )}
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        <div className="truncate text-sm text-slate-500 dark:text-slate-400">{label}</div>
        {hint && <div className="mt-0.5 truncate text-xs text-slate-400">{hint}</div>}
      </div>
    </Card>
  );
}
