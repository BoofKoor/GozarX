import { Timer } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/Card";
import { faPct, formatNumber, humanHours } from "@/lib/format";
import type { DashboardAnalytics } from "@/types/api";
import { useI18n } from "@/i18n";

/** How fast new users reach their first config, and what share activate same-day — the classic
 *  activation health check.
 *
 *  Both figures are WINDOWED on the page's range: the cohort is everyone whose first claim landed
 *  in it. They used to be all-time numbers sitting under a range control that could not move them,
 *  which made the control a lie for this card. */
export function ActivationPanel({ data }: { data: DashboardAnalytics }) {
  const { t } = useI18n();
  const median = data.median_hours_to_claim.value;
  return (
    <Card>
      <CardHeader title={t("d.activation")} icon={Timer} />
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl bg-surface-raised p-4">
          <div className="text-2xl font-bold tabular-nums">
            {/* `humanHours` carries the unit, and picks one that fits: the real median is 21
                seconds, which as a bare "hours" figure printed as 0. */}
            {median == null ? "—" : humanHours(median)}
          </div>
          <div className="mt-1 text-xs text-content-muted">{t("d.activation.median")}</div>
        </div>
        <div className="rounded-xl bg-surface-raised p-4">
          <div className="text-2xl font-bold tabular-nums text-brand">
            {faPct(data.activation_24h.value)}
          </div>
          <div className="mt-1 text-xs text-content-muted">{t("d.activation.24h")}</div>
        </div>
      </div>
      <p className="mt-3 text-xs text-content-subtle">
        {t("d.activation.note", {
          n: formatNumber(data.first_claimers_in_range),
          all: formatNumber(data.claimers_all_time),
        })}
      </p>
    </Card>
  );
}
