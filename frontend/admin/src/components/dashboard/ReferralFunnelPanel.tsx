import { GitBranch } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { faPct, formatNumber } from "@/lib/format";
import type { DashboardAnalytics } from "@/types/api";
import { useI18n } from "@/i18n";

/** The invitee side of referrals (from the previously-unused users.referred_by): how many joined via
 *  an invite and how many of those activated, plus the K-factor viral coefficient. */
export function ReferralFunnelPanel({ data }: { data: DashboardAnalytics }) {
  const { t } = useI18n();
  const r = data.referral;
  const claimedWidth = r.joined > 0 ? (r.joined_claimed / r.joined) * 100 : 0;
  const viral = r.k_factor >= 1;
  return (
    <Card>
      <CardHeader
        title={t("d.funnel")}
        icon={GitBranch}
        action={
          <Badge tone={viral ? "success" : "neutral"}>
            {t("d.funnel.k", { k: formatNumber(r.k_factor) })}
          </Badge>
        }
      />
      <div className="space-y-3">
        <Stage label={t("d.funnel.joined")} value={r.joined} width={100} tone="bg-brand/30" />
        <Stage
          label={t("d.funnel.claimed")}
          value={r.joined_claimed}
          width={claimedWidth}
          tone="bg-brand"
        />
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-content-subtle">
        <span>{t("d.funnel.conversion", { pct: faPct(r.invitee_conversion_pct) })}</span>
        <span>{viral ? t("d.funnel.viral") : t("d.funnel.notViral")}</span>
      </div>
      {/* The growth figure the radar used to carry. It reads against the users who COULD have been
          referred — everyone who signed up once the programme was producing rows — not the whole
          base, most of which predates it and can never have a referrer. */}
      <p className="mt-1.5 text-xs text-content-muted">
        {t("d.funnel.share", {
          pct: faPct(r.joined_share_pct),
          n: formatNumber(r.eligible),
        })}
      </p>
    </Card>
  );
}

function Stage({
  label,
  value,
  width,
  tone,
}: {
  label: string;
  value: number;
  width: number;
  tone: string;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-content-muted">{label}</span>
        <span className="font-medium tabular-nums text-content-muted">{formatNumber(value)}</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-surface-sunken">
        <div
          className={`h-full rounded-full transition-all ${tone}`}
          style={{ width: `${Math.max(2, Math.min(100, width))}%` }}
        />
      </div>
    </div>
  );
}
