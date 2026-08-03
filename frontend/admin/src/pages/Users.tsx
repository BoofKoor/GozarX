import { Search, UserX } from "lucide-react";
import { type ReactNode, useDeferredValue, useEffect, useState } from "react";
import { toast } from "sonner";

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
import { useUser, useUserAction, useUsers } from "@/hooks/useUsers";
import { faDate, formatNumber, langLabel } from "@/lib/format";
import type { UserAction } from "@/types/api";

const STATUS: Record<string, { label: string; tone: BadgeTone }> = {
  available: { label: "در دسترس", tone: "neutral" },
  active_config: { label: "فعال", tone: "success" },
  banned: { label: "مسدود", tone: "danger" },
};

const FILTERS = [
  { value: "", label: "همه" },
  { value: "available", label: "در دسترس" },
  { value: "active_config", label: "فعال" },
  { value: "banned", label: "مسدود" },
];

const PAGE_SIZE = 25;

function StatusBadge({ status }: { status: string }) {
  const meta = STATUS[status] ?? { label: status, tone: "neutral" as BadgeTone };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function Users() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<number | null>(null);
  const deferredSearch = useDeferredValue(search);

  useEffect(() => setPage(1), [status, deferredSearch]);

  const { data, isLoading, isError, refetch } = useUsers({
    page,
    page_size: PAGE_SIZE,
    status: status || undefined,
    search: deferredSearch || undefined,
  });

  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <PageHeader title="کاربران" sub={`${formatNumber(total)} کاربر ثبت‌شده در ربات`}>
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-[240px] flex-1">
            <Input
              aria-label="جستجوی کاربران"
              icon={<Search className="h-4 w-4" />}
              placeholder="جستجو با آیدی تلگرام یا یوزرنیم پنل…"
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
      </PageHeader>

      {/* Mounted only while a row is selected — the drawer's hooks (useConfirm, the detail query)
          have no reason to run on a closed panel. */}
      {detailId != null && <UserDetail id={detailId} onClose={() => setDetailId(null)} />}

      <Card padded={false} className="p-5">
        {isError && !data ? (
          <ErrorState compact onRetry={() => refetch()} />
        ) : isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner className="h-7 w-7 text-brand" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <EmptyState
            icon={UserX}
            title="کاربری یافت نشد"
            message={
              search || status
                ? "با این جستجو/فیلتر نتیجه‌ای نبود. فیلترها را بردارید."
                : "هنوز کسی ربات را استارت نکرده است."
            }
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>آیدی تلگرام</TH>
                <TH>وضعیت</TH>
                <TH>دعوت‌ها</TH>
                <TH>یوزرنیم پنل</TH>
                <TH>عضویت</TH>
              </TR>
            </THead>
            <TBody>
              {data.items.map((u) => (
                <TR
                  key={u.telegram_id}
                  onClick={() => setDetailId(u.telegram_id)}
                  selected={u.telegram_id === detailId}
                >
                  <TD className="font-mono" dir="ltr">
                    {u.telegram_id}
                  </TD>
                  <TD>
                    <StatusBadge status={u.status} />
                  </TD>
                  <TD className="tabular-nums">{formatNumber(u.referral_count)}</TD>
                  <TD className="font-mono text-xs text-content-muted" dir="ltr">
                    {u.panel_username ?? "—"}
                  </TD>
                  <TD className="whitespace-nowrap text-xs text-content-muted">
                    {faDate(u.created_at)}
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

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-2 border-b border-line py-2 text-sm last:border-0">
      <span className="text-content-muted">{label}</span>
      <span dir="ltr" className="text-content">
        {value}
      </span>
    </div>
  );
}

function UserDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const { data: user, isLoading } = useUser(id);
  const action = useUserAction();
  const confirm = useConfirm();

  async function run(name: UserAction, destructive = false) {
    if (
      destructive &&
      !(await confirm({
        message: "از انجام این عمل مطمئن هستید؟",
        tone: "danger",
        confirmLabel: "بله، انجام بده",
      }))
    ) {
      return;
    }
    action.mutate(
      { id, action: name },
      { onSuccess: () => toast.success("انجام شد."), onError: () => toast.error("ناموفق بود.") },
    );
  }

  return (
    <Drawer
      open
      onClose={onClose}
      title="کارت کاربر"
      sub={String(id)}
      footer={
        <Button variant="ghost" onClick={onClose}>
          بستن
        </Button>
      }
    >
      {isLoading || !user ? (
        <div className="flex justify-center py-10">
          <Spinner className="h-6 w-6 text-brand" />
        </div>
      ) : (
        <>
          <div>
            <DetailRow
              label="آیدی تلگرام"
              value={<span className="font-mono">{user.telegram_id}</span>}
            />
            <DetailRow label="وضعیت" value={<StatusBadge status={user.status} />} />
            <DetailRow label="زبان" value={langLabel(user.language)} />
            <DetailRow label="دعوت‌ها" value={formatNumber(user.referral_count)} />
            <DetailRow label="کانفیگ‌های گرفته‌شده" value={formatNumber(user.configs ?? 0)} />
            <DetailRow label="یوزرنیم پنل" value={user.panel_username ?? "—"} />
            <DetailRow label="معرف" value={user.referred_by ?? "—"} />
            <DetailRow label="عضویت" value={faDate(user.created_at)} />
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            {user.status === "banned" ? (
              <Button onClick={() => run("unban")} loading={action.isPending}>
                رفع مسدودی
              </Button>
            ) : (
              <Button variant="danger" onClick={() => run("ban", true)} loading={action.isPending}>
                مسدودسازی
              </Button>
            )}
            <Button variant="outline" onClick={() => run("reclaim")} loading={action.isPending}>
              اجازهٔ دریافت مجدد
            </Button>
            <Button
              variant="outline"
              onClick={() => run("zero_referrals", true)}
              loading={action.isPending}
            >
              صفر کردن دعوت‌ها
            </Button>
          </div>
        </>
      )}
    </Drawer>
  );
}
