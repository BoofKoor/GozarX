import { Fingerprint, Gift, MonitorSmartphone, Network, Search, ShieldOff, X } from "lucide-react";
import { type ReactNode, useDeferredValue, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Drawer } from "@/components/ui/Drawer";
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
import { apiErrorMessage } from "@/lib/api";
import { faDate, formatNumber } from "@/lib/format";
import type { SiteDeviceAction } from "@/types/api";

const STATUS: Record<string, { label: string; tone: BadgeTone }> = {
  available: { label: "آزاد", tone: "neutral" },
  active_config: { label: "دارای کانفیگ", tone: "success" },
  blocked: { label: "مسدود", tone: "danger" },
};

const FILTERS = [
  { value: "", label: "همه" },
  { value: "available", label: "آزاد" },
  { value: "active_config", label: "دارای کانفیگ" },
  { value: "blocked", label: "مسدود" },
];

const REWARD_LABEL: Record<string, string> = {
  pwa: "نصب اپ (PWA)",
  push: "فعال‌کردن اعلان",
};

const PAGE_SIZE = 25;

function StatusBadge({ status }: { status: string }) {
  const meta = STATUS[status] ?? { label: status, tone: "neutral" as BadgeTone };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

/**
 * The website's users, finally visible.
 *
 * There was no admin surface for site devices at all: the anti-abuse analytics counted shared
 * fingerprints and busy IP buckets while naming none of the devices, and there was no way to stop
 * an abuser. `?ip_bucket=` is what that panel deep-links into.
 */
export function SiteDevices() {
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
        title="دستگاه‌های وب‌سایت"
        sub={`${formatNumber(total)} دستگاه${ipBucket ? " در این محدودهٔ IP" : ""}`}
      >
        <SiteTabs />
      </PageHeader>

      {selected && <DeviceDrawer uuid={selected} onClose={() => setSelected(null)} />}

      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[240px] flex-1">
          <Input
            aria-label="جستجوی دستگاه‌ها"
            icon={<Search className="h-4 w-4" />}
            placeholder="جستجو با شناسه (GZ-…)، uuid یا نام کاربری پنل…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Segmented
          value={status}
          onChange={setStatus}
          options={FILTERS}
          size="sm"
          ariaLabel="فیلتر وضعیت"
        />
      </div>

      {ipBucket && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl bg-warning-500/15 px-3 py-2 text-xs text-warning-700">
          <Network className="h-4 w-4 shrink-0" />
          فقط دستگاه‌های پشت IP <span className="font-mono">{ipBucket}</span>
          <Button
            variant="ghost"
            size="xs"
            onClick={() => {
              params.delete("ip_bucket");
              setParams(params, { replace: true });
            }}
          >
            <X className="h-3.5 w-3.5" />
            برداشتن فیلتر
          </Button>
        </div>
      )}

      <Card>
        {isError && !data ? (
          <ErrorState compact onRetry={() => refetch()} />
        ) : isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner className="h-7 w-7 text-brand" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={MonitorSmartphone}
            title="دستگاهی یافت نشد"
            message={
              search || status || ipBucket
                ? "با این جستجو/فیلتر نتیجه‌ای نبود."
                : "هنوز کسی از سایت عمومی کانفیگ نگرفته است."
            }
          />
        ) : (
          <Table minWidth="min-w-[720px]">
            <THead>
              <TR>
                <TH>شناسه</TH>
                <TH>وضعیت</TH>
                <TH>دعوت‌ها</TH>
                <TH>استریک</TH>
                <TH>آخرین دریافت</TH>
                <TH>محدودهٔ IP</TH>
                <TH>اولین بازدید</TH>
              </TR>
            </THead>
            <TBody>
              {data.items.map((d) => (
                <TR key={d.uuid} onClick={() => setSelected(d.uuid)} selected={d.uuid === selected}>
                  <TD>
                    <span className="font-mono text-xs" dir="ltr">
                      {d.handle ?? d.uuid.slice(0, 8)}
                    </span>
                    {d.has_fingerprint && (
                      <Fingerprint
                        className="ms-1.5 inline h-3.5 w-3.5 text-content-subtle"
                        aria-label="اثرانگشت مرورگر ثبت شده"
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
        <Pagination page={page} totalPages={pages} onChange={setPage} className="mt-4" />
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
  const { data: device, isLoading } = useSiteDevice(uuid);
  const { data: peers } = useSiteDevicePeers(uuid);
  const action = useSiteDeviceAction();
  const confirm = useConfirm();

  async function run(name: SiteDeviceAction, message?: string) {
    if (message && !(await confirm({ message, tone: "danger", confirmLabel: "بله، انجام بده" }))) {
      return;
    }
    action.mutate(
      { uuid, action: name },
      {
        onSuccess: () => toast.success("انجام شد."),
        onError: (err) => toast.error(apiErrorMessage(err, "ناموفق بود.")),
      },
    );
  }

  return (
    <Drawer
      open
      onClose={onClose}
      title={device?.handle ?? "دستگاه"}
      sub={uuid}
      footer={
        <Button variant="ghost" onClick={onClose}>
          بستن
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
            <Row label="وضعیت" value={<StatusBadge status={device.status} />} />
            <Row label="کانفیگ‌های گرفته‌شده" value={formatNumber(device.claims)} />
            <Row label="آخرین دریافت" value={faDate(device.last_claim_at)} />
            <Row label="دعوت‌های پاداش‌گرفته" value={formatNumber(device.referral_count)} />
            <Row label="کل دعوت‌شده‌ها" value={formatNumber(device.invited)} />
            <Row label="استریک روزانه" value={formatNumber(device.streak_count)} />
            <Row label="حساب پنل" value={device.site_panel_username ?? "—"} />
            <Row label="محدودهٔ IP" value={device.ip_bucket ?? "—"} />
            <Row label="اولین بازدید" value={faDate(device.created_at)} />
          </div>

          {device.rewards.length > 0 && (
            <section>
              <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-content">
                <Gift className="h-4 w-4 text-content-subtle" />
                پاداش‌های یک‌باره
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {device.rewards.map((r) => (
                  <Badge key={r} tone="brand">
                    {REWARD_LABEL[r] ?? r}
                  </Badge>
                ))}
              </div>
            </section>
          )}

          <section>
            <h3 className="mb-2 text-sm font-semibold text-content">آخرین دریافت‌ها</h3>
            {device.recent_claims.length === 0 ? (
              <p className="text-xs text-content-muted">هنوز کانفیگی نگرفته است.</p>
            ) : (
              <ul className="space-y-1.5">
                {device.recent_claims.map((c, i) => (
                  <li
                    key={`${c.created_at}-${i}`}
                    className="flex items-center justify-between rounded-lg bg-surface-sunken px-3 py-1.5 text-xs"
                  >
                    <span dir="auto" className="text-content">
                      {c.location}
                      {c.is_change && (
                        <span className="ms-1.5 text-content-subtle">(تغییر لوکیشن)</span>
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
                دستگاه‌های با اثرانگشت مشترک
              </h3>
              <ul className="space-y-1.5">
                {peers.map((p) => (
                  <li
                    key={p.uuid}
                    className="flex items-center justify-between rounded-lg bg-surface-sunken px-3 py-1.5 text-xs"
                  >
                    <span className="font-mono" dir="ltr">
                      {p.handle ?? p.uuid.slice(0, 8)}
                    </span>
                    <StatusBadge status={p.status} />
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-content-muted">
                فقط یک نشانه است، نه اثبات تقلب — چند نفر پشت یک مرورگر مشترک هم همین را می‌سازند.
              </p>
            </section>
          )}

          <div className="flex flex-wrap gap-2 border-t border-line pt-4">
            {device.status === "blocked" ? (
              <Button onClick={() => run("unblock")} loading={action.isPending}>
                رفع مسدودی
              </Button>
            ) : (
              <Button
                variant="danger"
                loading={action.isPending}
                onClick={() =>
                  run("block", "این دستگاه مسدود شود؟ کانفیگ فعالش هم همین حالا باطل می‌شود.")
                }
              >
                <ShieldOff className="h-4 w-4" />
                مسدودسازی
              </Button>
            )}
            <Button variant="outline" onClick={() => run("reset")} loading={action.isPending}>
              اجازهٔ دریافت مجدد
            </Button>
          </div>
        </div>
      )}
    </Drawer>
  );
}
