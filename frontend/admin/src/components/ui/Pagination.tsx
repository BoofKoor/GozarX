import { ChevronLeft, ChevronRight } from "lucide-react";

import { useI18n } from "@/i18n";
import { formatNumber } from "@/lib/format";

import { Button } from "./Button";

/**
 * Page stepper.
 *
 * The chevrons follow the READING direction, which means they have to mirror: "previous" points
 * left in English and right in Persian. Hardcoded for one of the two — as they were, drawn for RTL
 * — the English panel showed "previous" pointing forward and "next" pointing back.
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
  const { t } = useI18n();
  if (totalPages <= 1) return null;
  return (
    <div className={className}>
      <div className="flex items-center justify-between gap-2">
        <Button
          variant="outline"
          size="sm"
          iconOnly
          aria-label={t("ui.prevPage")}
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft className="h-4 w-4 rtl:-scale-x-100" />
        </Button>
        <span className="text-xs tabular-nums text-content-muted">
          {t("ui.pageOf", { n: formatNumber(page), total: formatNumber(totalPages) })}
        </span>
        <Button
          variant="outline"
          size="sm"
          iconOnly
          aria-label={t("ui.nextPage")}
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
        >
          <ChevronRight className="h-4 w-4 rtl:-scale-x-100" />
        </Button>
      </div>
    </div>
  );
}
