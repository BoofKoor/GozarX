import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "./Button";
import { Card } from "./Card";

/**
 * Shared failure state for a query that errored. Pages must render this on `isError` rather than
 * falling through to their empty state — otherwise a failed fetch reads as "no data" (misleading)
 * or, worse, spins forever. Optional `onRetry` wires the query's `refetch`.
 */
export function ErrorState({
  message = "دریافت اطلاعات با خطا مواجه شد. لطفاً دوباره تلاش کنید.",
  onRetry,
  compact = false,
}: {
  message?: string;
  onRetry?: () => void;
  /** Render inline (no Card wrapper) — for use inside a card that owns its own chrome. */
  compact?: boolean;
}) {
  const body = (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-danger-500/12 text-danger-700">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <p className="max-w-sm text-sm text-content-muted">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw className="h-4 w-4" />
          تلاش مجدد
        </Button>
      )}
    </div>
  );
  return compact ? body : <Card>{body}</Card>;
}
