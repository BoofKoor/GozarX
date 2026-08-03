import { ChevronLeft, ChevronRight } from "lucide-react";

import { formatNumber } from "@/lib/format";

import { Button } from "./Button";

/**
 * Page stepper. RTL note: "previous" points RIGHT and "next" points LEFT — the chevrons are chosen
 * to match reading direction, not the LTR convention.
 */
export function Pagination({
  page,
  totalPages,
  onChange,
  className,
}: {
  page: number;
  totalPages: number;
  onChange: (next: number) => void;
  className?: string;
}) {
  if (totalPages <= 1) return null;
  return (
    <div className={className}>
      <div className="flex items-center justify-between gap-2">
        <Button
          variant="outline"
          size="sm"
          iconOnly
          aria-label="صفحهٔ قبل"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <span className="text-xs tabular-nums text-content-muted">
          صفحهٔ {formatNumber(page)} از {formatNumber(totalPages)}
        </span>
        <Button
          variant="outline"
          size="sm"
          iconOnly
          aria-label="صفحهٔ بعد"
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
