import { GitBranch } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { faPct, formatNumber } from "@/lib/format";
import type { DashboardAnalytics } from "@/types/api";

/** The invitee side of referrals (from the previously-unused users.referred_by): how many joined via
 *  an invite and how many of those activated, plus the K-factor viral coefficient. */
export function ReferralFunnelPanel({ data }: { data: DashboardAnalytics }) {
  const r = data.referral;
  const claimedWidth = r.joined > 0 ? (r.joined_claimed / r.joined) * 100 : 0;
  const viral = r.k_factor >= 1;
  return (
    <Card>
      <CardHeader
        title="قیف دعوت"
        icon={GitBranch}
        action={
          <Badge tone={viral ? "success" : "neutral"}>ضریب K: {formatNumber(r.k_factor)}</Badge>
        }
      />
      <div className="space-y-3">
        <Stage label="کاربرانِ دعوت‌شده" value={r.joined} width={100} tone="bg-brand/30" />
        <Stage
          label="از آن‌ها کانفیگ گرفتند"
          value={r.joined_claimed}
          width={claimedWidth}
          tone="bg-brand"
        />
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
        <span>نرخ تبدیل دعوت‌شده‌ها: {faPct(r.invitee_conversion_pct)}</span>
        <span>{viral ? "رشد خودپایدار (K ≥ ۱)" : "K < ۱"}</span>
      </div>
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
        <span className="text-slate-600 dark:text-slate-300">{label}</span>
        <span className="font-medium tabular-nums text-slate-500">{formatNumber(value)}</span>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        <div
          className={`h-full rounded-full transition-all ${tone}`}
          style={{ width: `${Math.max(2, Math.min(100, width))}%` }}
        />
      </div>
    </div>
  );
}
