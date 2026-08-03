import { clsx } from "clsx";
import type { ComponentType, ReactNode } from "react";

/**
 * "Nothing here yet" state. Distinct from `ErrorState` on purpose: a failed fetch must never render
 * as an empty list, because the two need opposite responses from the admin (retry vs. create).
 */
export function EmptyState({
  icon: Icon,
  title,
  message,
  action,
  className,
}: {
  icon?: ComponentType<{ className?: string }>;
  title: ReactNode;
  message?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("flex flex-col items-center gap-3 px-6 py-12 text-center", className)}>
      {Icon && (
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-sunken text-content-subtle">
          <Icon className="h-6 w-6" />
        </div>
      )}
      <div>
        <p className="text-sm font-medium text-content">{title}</p>
        {message && <p className="mt-1 max-w-sm text-xs text-content-muted">{message}</p>}
      </div>
      {action}
    </div>
  );
}
