import { AlertTriangle, CheckCircle2, Webhook } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { formatNumber } from "@/lib/format";
import type { Probe, WebhookHealth } from "@/types/api";

export function WebhookCard({ webhook, telegram }: { webhook: WebhookHealth; telegram: Probe }) {
  // Match the backend's overall-status threshold: health.py marks the service degraded only when
  // pending EXCEEDS 50 (_PENDING_BACKLOG), so this card must stay "healthy" through 50 too — else at
  // exactly 50 the banner reads "سالم" while this badge contradicts it with "بررسی شود".
  const healthy =
    webhook.configured && telegram.ok && !webhook.recent_error && webhook.pending <= 50;
  return (
    <Card>
      <CardHeader
        title="پاسخگویی وبهوک تلگرام"
        icon={Webhook}
        action={
          <Badge tone={healthy ? "success" : webhook.configured ? "warning" : "neutral"}>
            {healthy ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5" /> سالم
              </>
            ) : webhook.configured ? (
              <>
                <AlertTriangle className="h-3.5 w-3.5" /> بررسی شود
              </>
            ) : (
              "غیرفعال"
            )}
          </Badge>
        }
      />
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <Row label="آدرس وبهوک" value={webhook.url_set ? "تنظیم شده" : "تنظیم نشده"} />
        <Row
          label="تأخیر API تلگرام"
          value={telegram.latency_ms != null ? `${telegram.latency_ms} ms` : "—"}
        />
        <Row label="آپدیت‌های معلق" value={formatNumber(webhook.pending)} />
        <Row
          label="خطای اخیر"
          value={webhook.recent_error ? "بله (۵ دقیقهٔ اخیر)" : "خیر"}
          danger={webhook.recent_error}
        />
      </dl>
      {webhook.last_error && (
        <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs dark:bg-slate-800/60" dir="ltr">
          <div className="mb-0.5 text-slate-400">
            last error{" "}
            {webhook.last_error_at
              ? `· ${new Date(webhook.last_error_at).toLocaleString("fa-IR")}`
              : ""}
          </div>
          <code className="text-danger-600 dark:text-danger-500">{webhook.last_error}</code>
        </div>
      )}
    </Card>
  );
}

function Row({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 pb-1.5 dark:border-slate-800">
      <dt className="text-slate-500">{label}</dt>
      <dd className={danger ? "font-medium text-danger-600 dark:text-danger-500" : "font-medium"}>
        {value}
      </dd>
    </div>
  );
}
