import { AlertTriangle, CheckCircle2, Webhook } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { useI18n } from "@/i18n";
import { faDateTime, formatMs, formatNumber } from "@/lib/format";
import type { Probe, WebhookHealth } from "@/types/api";

export function WebhookCard({ webhook, telegram }: { webhook: WebhookHealth; telegram: Probe }) {
  const { t } = useI18n();
  // Match the backend's overall-status threshold: health.py marks the service degraded only when
  // pending EXCEEDS 50 (_PENDING_BACKLOG), so this card must stay "healthy" through 50 too — else at
  // exactly 50 the banner would read "healthy" while this badge contradicted it.
  const healthy =
    webhook.configured && telegram.ok && !webhook.recent_error && webhook.pending <= 50;
  return (
    <Card>
      <CardHeader
        title={t("sys.wh.title")}
        icon={Webhook}
        action={
          <Badge tone={healthy ? "success" : webhook.configured ? "warning" : "neutral"}>
            {healthy ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5" /> {t("sys.wh.ok")}
              </>
            ) : webhook.configured ? (
              <>
                <AlertTriangle className="h-3.5 w-3.5" /> {t("sys.wh.check")}
              </>
            ) : (
              t("sys.wh.off")
            )}
          </Badge>
        }
      />
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <Row
          label={t("sys.wh.url")}
          value={webhook.url_set ? t("sys.wh.urlSet") : t("sys.wh.urlUnset")}
        />
        <Row
          label={t("sys.wh.latency")}
          value={
            // `88 ms` reordered to `ms 88` beside Persian — a unit belongs after its number.
            // The isolate now travels with the string (`formatMs`), so this is the same reading
            // the dashboard's health list and the probe chips print, formatted in one place.
            telegram.latency_ms != null ? (
              <span className="tabular-nums">{formatMs(telegram.latency_ms)}</span>
            ) : (
              "—"
            )
          }
        />
        <Row label={t("sys.wh.pending")} value={formatNumber(webhook.pending)} />
        <Row
          label={t("sys.wh.recentError")}
          value={webhook.recent_error ? t("sys.wh.recentErrorYes") : t("sys.wh.recentErrorNo")}
          danger={webhook.recent_error}
        />
      </dl>
      {webhook.last_error && (
        <div className="mt-3 rounded-lg bg-surface-raised p-3 text-xs" dir="ltr">
          <div className="mb-0.5 text-content-subtle">
            {t("sys.wh.lastError")}{" "}
            {webhook.last_error_at ? `· ${faDateTime(webhook.last_error_at)}` : ""}
          </div>
          <code className="text-danger-700">{webhook.last_error}</code>
        </div>
      )}
    </Card>
  );
}

function Row({ label, value, danger }: { label: string; value: ReactNode; danger?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-line pb-1.5">
      <dt className="text-content-muted">{label}</dt>
      <dd className={danger ? "font-medium text-danger-700" : "font-medium"}>{value}</dd>
    </div>
  );
}
