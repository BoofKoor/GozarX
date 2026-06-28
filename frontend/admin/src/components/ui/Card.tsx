import { clsx } from "clsx";
import type { ReactNode } from "react";

interface CardProps {
  className?: string;
  children: ReactNode;
  /** Drop the default inner padding (for cards that own their own layout, e.g. a table). */
  padded?: boolean;
  /** Lift + accent border on hover — for clickable/linked cards. */
  interactive?: boolean;
}

export function Card({ className, children, padded = true, interactive = false }: CardProps) {
  return (
    <div
      className={clsx(
        "rounded-2xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900",
        padded && "p-5",
        interactive &&
          "transition hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-card-hover",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Optional header row for a card: a title (+ optional icon) on one side, actions on the other. */
export function CardHeader({
  title,
  icon: Icon,
  action,
  className,
}: {
  title: ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("mb-4 flex items-center justify-between gap-3", className)}>
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
        {Icon && <Icon className="h-4 w-4 text-slate-400" />}
        {title}
      </div>
      {action}
    </div>
  );
}
