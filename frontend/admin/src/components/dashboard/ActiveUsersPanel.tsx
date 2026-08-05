import { Activity } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { faPct, formatNumber } from "@/lib/format";
import type { DashboardAnalytics } from "@/types/api";
import { useI18n } from "@/i18n";

/** Active-user tiles (DAU/WAU/MAU) + stickiness = DAU/MAU. A real engagement signal beyond raw
 *  claim counts: the share of the monthly base that comes back on a given day. */
export function ActiveUsersPanel({ data }: { data: DashboardAnalytics }) {
  const { t } = useI18n();
  const tiles = [
    { label: t("d.active.daily"), sub: "DAU", value: data.dau },
    { label: t("d.active.weekly"), sub: "WAU", value: data.wau },
    { label: t("d.active.monthly"), sub: "MAU", value: data.mau },
  ];
  return (
    <Card>
      <CardHeader
        title={t("d.active")}
        icon={Activity}
        action={
          <Badge tone="brand">
            {t("d.active.stickiness", { pct: faPct(data.stickiness_pct) })}
          </Badge>
        }
      />
      <div className="grid grid-cols-3 gap-3">
        {tiles.map((t) => (
          <div key={t.sub} className="rounded-xl bg-surface-raised p-3 text-center">
            <div className="text-xl font-bold tabular-nums">{formatNumber(t.value)}</div>
            <div className="mt-0.5 text-xs text-content-muted">{t.label}</div>
            <div className="text-[10px] uppercase tracking-wide text-content-subtle" dir="ltr">
              {t.sub}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-content-subtle">{t("d.active.note")}</p>
    </Card>
  );
}
