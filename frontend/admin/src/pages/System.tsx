import { useState } from "react";

import { HealthBanner } from "@/components/system/HealthBanner";
import { HistoryChart } from "@/components/system/HistoryChart";
import { GozarHostCard, PanelHostCard } from "@/components/system/ResourceGauges";
import { WebhookCard } from "@/components/system/WebhookCard";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useSystemHealth, useSystemHistory } from "@/hooks/useSystem";

export function System() {
  const [minutes, setMinutes] = useState(60);
  const { data: health, isLoading, isError } = useSystemHealth();
  const { data: history = [] } = useSystemHistory(minutes);

  if (isLoading) {
    return <SystemSkeleton />;
  }
  if (isError || !health) {
    return <Card>خطا در دریافت وضعیت سیستم. لطفاً بعداً تلاش کنید.</Card>;
  }

  return (
    <div className="space-y-6">
      <PageHeader title="سیستم" />
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
  return (
    <div className="space-y-6">
      <PageHeader title="سیستم" />
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
