import { Gift } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber } from "@/lib/format";
import type { Referrer } from "@/types/api";

export function TopReferrers({ data }: { data: Referrer[] }) {
  return (
    <Card>
      <CardHeader title="برترین دعوت‌کننده‌ها" icon={Gift} />
      {data.length === 0 ? (
        <div className="flex h-40 items-center justify-center text-sm text-content-subtle">
          هنوز دعوتی ثبت نشده
        </div>
      ) : (
        <ul className="divide-y divide-line">
          {data.map((r, i) => (
            <li key={r.telegram_id} className="flex items-center gap-3 py-2.5">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-sunken text-xs font-bold text-content-muted tabular-nums">
                {i + 1}
              </span>
              <code className="flex-1 text-sm text-content-muted" dir="ltr">
                {r.telegram_id}
              </code>
              <Badge tone="brand">{formatNumber(r.referral_count)} دعوت</Badge>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
