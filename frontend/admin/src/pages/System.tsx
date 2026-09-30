import { AlertTriangle } from "lucide-react";
import { useState } from "react";

import { HealthBanner } from "@/components/system/HealthBanner";
import { HistoryChart } from "@/components/system/HistoryChart";
import { GozarHostCard, PanelHostCard } from "@/components/system/ResourceGauges";
import { WebhookCard } from "@/components/system/WebhookCard";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useSystemHealth, useSystemHistory } from "@/hooks/useSystem";
import { useI18n } from "@/i18n";
import { faTime } from "@/lib/format";

export function System() {
  const { t } = useI18n();
  const [minutes, setMinutes] = useState(60);
  const { data: health, isLoading, isError, refetch, dataUpdatedAt } = useSystemHealth(10_000);
  const { data: history = [] } = useSystemHistory(minutes);

  if (isLoading) {
    return <SystemSkeleton />;
  }
  // The error PAGE only when there is nothing to show: on a 10-second poll, one missed probe during
  // a deploy used to swap the whole live page for an error card.
  if (!health) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("sys.title")} />
        {/* ErrorState, not an EmptyState: a probe that could not be read needs a retry, and the
            two states call for opposite responses. */}
        <ErrorState message={t("sys.unreachable")} onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t("sys.title")} sub={t("sys.sub")} />
      {isError && (
        <div
          role="status"
          className="flex flex-wrap items-center gap-2 rounded-xl bg-warning-500/15 px-3 py-2 text-xs text-warning-700"
        >
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className="min-w-0 flex-1">
            {t("sys.stale", { time: faTime(new Date(dataUpdatedAt).toISOString()) })}
          </span>
          <Button variant="ghost" size="xs" onClick={() => refetch()}>
            {t("ui.retry")}
          </Button>
        </div>
      )}
      <HealthBanner data={health} />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <GozarHostCard host={health.host} />
        <PanelHostCard panel={health.panel_stats} />
      </div>
      <WebhookCard webhook={health.webhook} telegram={health.telegram} />
      <HistoryChart samples={history} minutes={minutes} onMinutesChange={setMinutes} />
    </div>
  );
}

function SystemSkeleton() {
  const { t } = useI18n();
  return (
    <div className="space-y-6">
      <PageHeader title={t("sys.title")} sub={t("sys.sub")} />
      <Card>
        <Skeleton className="h-16 w-full" />
      </Card>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <Skeleton className="h-40 w-full" />
        </Card>
        <Card>
          <Skeleton className="h-40 w-full" />
        </Card>
      </div>
      <Card>
        <Skeleton className="h-60 w-full" />
      </Card>
    </div>
  );
}
