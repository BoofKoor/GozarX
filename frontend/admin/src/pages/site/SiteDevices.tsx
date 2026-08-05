import { Fingerprint, Gift, MonitorSmartphone, Network, Search, ShieldOff, X } from "lucide-react";
import { type ReactNode, useDeferredValue, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { RecordDialog } from "@/components/ui/RecordDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Segmented } from "@/components/ui/Segmented";
import { Spinner } from "@/components/ui/Spinner";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/Table";
import { useConfirm } from "@/components/ui/confirm";
import {
  useSiteDevice,
  useSiteDeviceAction,
  useSiteDevicePeers,
  useSiteDevices,
} from "@/hooks/useSite";
import { useI18n, type MessageKey } from "@/i18n";
import { apiErrorMessage } from "@/lib/api";
import { faDate, formatNumber } from "@/lib/format";
import type { SiteDeviceAction } from "@/types/api";

const STATUS: Record<string, { label: MessageKey; tone: BadgeTone }> = {
  available: { label: "sd.status.available", tone: "neutral" },
  active_config: { label: "sd.status.active_config", tone: "success" },
  blocked: { label: "sd.status.blocked", tone: "danger" },
};

const REWARD_LABEL: Record<string, MessageKey> = {
  pwa: "sd.reward.pwa",
  push: "sd.reward.push",
};

const PAGE_SIZE = 25;

function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const meta = STATUS[status];
  return <Badge tone={meta?.tone ?? "neutral"}>{meta ? t(meta.label) : status}</Badge>;
}

/**
 * The website's users, finally visible.
 *
 * There was no admin surface for site devices at all: the anti-abuse analytics counted shared
 * fingerprints and busy IP buckets while naming none of the devices, and there was no way to stop
 * an abuser. `?ip_bucket=` is what that panel deep-links into.
 */
export function SiteDevices() {
  const { t } = useI18n();
  const FILTERS = [
    { value: "", label: t("sd.filter.all") },
    { value: "available", label: t("sd.status.available") },
    { value: "active_config", label: t("sd.status.active_config") },
    { value: "blocked", label: t("sd.status.blocked") },
  ];
  const [params, setParams] = useSearchParams();
  const ipBucket = params.get("ip_bucket") ?? "";
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const deferredSearch = useDeferredValue(search);

  useEffect(() => setPage(1), [status, deferredSearch, ipBucket]);

  const { data, isLoading, isError, refetch } = useSiteDevices({
    page,
    page_size: PAGE_SIZE,
    status: status || undefined,
    search: deferredSearch || undefined,
    ip_bucket: ipBucket || undefined,
  });

  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("sd.title")}
        sub={t(ipBucket ? "sd.sub.ip" : "sd.sub", { n: formatNumber(total) })}
      >
        <SiteTabs />
      </PageHeader>

      {selected && <DeviceDrawer uuid={selected} onClose={() => setSelected(null)} />}

      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[240px] flex-1">
          <Input
            aria-label={t("sd.searchAria")}
            icon={<Search className="h-4 w-4" />}
            placeholder={t("sd.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Segmented
          value={status}
          onChange={setStatus}
          options={FILTERS}
          size="sm"
          ariaLabel={t("sd.filterAria")}
        />
      </div>

      {ipBucket && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl bg-warning-500/15 px-3 py-2 text-xs text-warning-700">
          <Network className="h-4 w-4 shrink-0" />
          {t("sd.ipFilter")}{" "}
          <span className="font-mono" dir="ltr">
            {ipBucket}
          </span>
          <Button
            variant="ghost"
            size="xs"
            onClick={() => {
              params.delete("ip_bucket");
              setParams(params, { replace: true });
            }}
          >
            <X className="h-3.5 w-3.5" />
            {t("sd.ipFilter.clear")}
          </Button>
        </div>
      )}

      {/* Unpadded and clipped: the table is flush with the card so its header band can run the
          full width, exactly as on Users. */}
      <Card padded={false} className="overflow-hidden">
        {isError && !data ? (
          <div className="p-card">
            <ErrorState compact onRetry={() => refetch()} />
          </div>
        ) : isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner className="h-7 w-7 text-brand" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="p-card">
            <EmptyState
              icon={MonitorSmartphone}
              title={t("sd.empty")}
              message={search || status || ipBucket ? t("sd.empty.filtered") : t("sd.empty.none")}
            />
          </div>
        ) : (
          <Table label={t("sd.table.aria")} minWidth="min-w-[720px]">
            <THead>
              <TR>
                <TH>{t("sd.col.handle")}</TH>
                <TH>{t("sd.col.status")}</TH>
                <TH>{t("sd.col.invites")}</TH>
                <TH>{t("sd.col.streak")}</TH>
                <TH>{t("sd.col.lastClaim")}</TH>
                <TH>{t("sd.col.ip")}</TH>
                <TH>{t("sd.col.firstSeen")}</TH>
              </TR>
            </THead>
            <TBody>
              {data.items.map((d) => (
                <TR
                  key={d.uuid}
                  onClick={() => setSelected(d.uuid)}
                  selected={d.uuid === selected}
                  label={t("sd.row.open", { handle: d.handle ?? d.uuid })}
                >
                  <TD>
                    <span className="font-mono text-xs" dir="ltr">
                      {d.handle ?? d.uuid.slice(0, 8)}
                    </span>
                    {d.has_fingerprint && (
                      <Fingerprint
                        className="ms-1.5 inline h-3.5 w-3.5 text-content-subtle"
                        aria-label={t("sd.fingerprint")}
                      />
                    )}
                  </TD>
                  <TD>
                    <StatusBadge status={d.status} />
                  </TD>
                  <TD className="tabular-nums">{formatNumber(d.referral_count)}</TD>
                  <TD className="tabular-nums">{formatNumber(d.streak_count)}</TD>
                  <TD className="whitespace-nowrap text-xs text-content-muted">
                    {faDate(d.last_claim_at)}
                  </TD>
                  <TD className="font-mono text-xs text-content-muted" dir="ltr">
                    {d.ip_bucket ?? "—"}
                  </TD>
                  <TD className="whitespace-nowrap text-xs text-content-muted">
                    {faDate(d.created_at)}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
        <div className="border-t border-line px-card py-2">
          <Pagination page={page} totalPages={pages} onChange={setPage} />
        </div>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-2 border-b border-line py-2 text-sm last:border-0">
      <span className="text-content-muted">{label}</span>
      <span dir="ltr" className="text-content">
        {value}
      </span>
    </div>
  );
}

function DeviceDrawer({ uuid, onClose }: { uuid: string; onClose: () => void }) {
  const { t } = useI18n();
  const { data: device, isLoading } = useSiteDevice(uuid);
  const { data: peers } = useSiteDevicePeers(uuid);
  const action = useSiteDeviceAction();
  const confirm = useConfirm();

  async function run(name: SiteDeviceAction, message?: string) {
    if (
      message &&
      !(await confirm({ message, tone: "danger", confirmLabel: t("sd.action.confirmLabel") }))
    ) {
      return;
    }
    action.mutate(
      { uuid, action: name },
      {
        onSuccess: () => toast.success(t("sd.action.done")),
        onError: (err) => toast.error(apiErrorMessage(err, t("sd.action.failed"))),
      },
    );
  }

  return (
    <RecordDialog
      open
      onClose={onClose}
      title={device?.handle ?? t("sd.detail.title")}
      sub={uuid}
      footer={
        <Button variant="ghost" onClick={onClose}>
          {t("ui.close")}
        </Button>
      }
    >
      {isLoading || !device ? (
        <div className="flex justify-center py-10">
          <Spinner className="h-6 w-6 text-brand" />
        </div>
      ) : (
        <div className="space-y-5">
          <div>
            <Row label={t("sd.col.status")} value={<StatusBadge status={device.status} />} />
            <Row label={t("sd.detail.claims")} value={formatNumber(device.claims)} />
            <Row label={t("sd.col.lastClaim")} value={faDate(device.last_claim_at)} />
            <Row
              label={t("sd.detail.rewardedInvites")}
              value={formatNumber(device.referral_count)}
            />
            <Row label={t("sd.detail.invited")} value={formatNumber(device.invited)} />
            <Row label={t("sd.detail.streak")} value={formatNumber(device.streak_count)} />
            <Row label={t("sd.detail.panelAccount")} value={device.site_panel_username ?? "—"} />
            <Row label={t("sd.col.ip")} value={device.ip_bucket ?? "—"} />
            <Row label={t("sd.col.firstSeen")} value={faDate(device.created_at)} />
          </div>

          {device.rewards.length > 0 && (
            <section>
              <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-content">
                <Gift className="h-4 w-4 text-content-subtle" />
                {t("sd.detail.oneOff")}
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {device.rewards.map((r) => (
                  <Badge key={r} tone="brand">
                    {REWARD_LABEL[r] ? t(REWARD_LABEL[r]) : r}
                  </Badge>
                ))}
              </div>
            </section>
          )}

          <section>
            <h3 className="mb-2 text-sm font-semibold text-content">
              {t("sd.detail.recentClaims")}
            </h3>
            {device.recent_claims.length === 0 ? (
              <p className="text-xs text-content-muted">{t("sd.detail.noClaims")}</p>
            ) : (
              <ul className="space-y-1.5">
                {device.recent_claims.map((c, i) => (
                  <li
                    key={`${c.created_at}-${i}`}
                    className="flex items-center justify-between rounded-lg bg-surface-raised px-3 py-1.5 text-xs"
                  >
                    <span dir="auto" className="text-content">
                      {c.location}
                      {c.is_change && (
                        <span className="ms-1.5 text-content-subtle">
                          {t("sd.detail.relocated")}
                        </span>
                      )}
                    </span>
                    <span className="text-content-muted">{faDate(c.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {peers && peers.length > 0 && (
            <section>
              <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-content">
                <Fingerprint className="h-4 w-4 text-content-subtle" />
                {t("sd.detail.sharedFp")}
              </h3>
              <ul className="space-y-1.5">
                {peers.map((p) => (
                  <li
                    key={p.uuid}
                    className="flex items-center justify-between rounded-lg bg-surface-raised px-3 py-1.5 text-xs"
                  >
                    <span className="font-mono" dir="ltr">
                      {p.handle ?? p.uuid.slice(0, 8)}
                    </span>
                    <StatusBadge status={p.status} />
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-content-muted">{t("sd.detail.sharedFpNote")}</p>
            </section>
          )}

          <div className="flex flex-wrap gap-2 border-t border-line pt-4">
            {device.status === "blocked" ? (
              <Button onClick={() => run("unblock")} loading={action.isPending}>
                {t("sd.action.unblock")}
              </Button>
            ) : (
              <Button
                variant="danger"
                loading={action.isPending}
                onClick={() => run("block", t("sd.action.blockConfirm"))}
              >
                <ShieldOff className="h-4 w-4" />
                {t("sd.action.block")}
              </Button>
            )}
            <Button variant="outline" onClick={() => run("reset")} loading={action.isPending}>
              {t("sd.action.reset")}
            </Button>
          </div>
        </div>
      )}
    </RecordDialog>
  );
}
