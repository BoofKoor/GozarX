import { Gift, Search, Ticket, UserX } from "lucide-react";
import { type ReactNode, useDeferredValue, useEffect, useState } from "react";
import { toast } from "sonner";

import { Avatar } from "@/components/ui/Avatar";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { RecordDialog } from "@/components/ui/RecordDialog";
import { Segmented } from "@/components/ui/Segmented";
import { Spinner } from "@/components/ui/Spinner";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/Table";
import { useConfirm } from "@/components/ui/confirm";
import { useUser, useUserAction, useUsers } from "@/hooks/useUsers";
import { useI18n, type MessageKey } from "@/i18n";
import { faDate, formatNumber, langLabel } from "@/lib/format";
import type { UserAction } from "@/types/api";

const STATUS: Record<string, { key: MessageKey; tone: BadgeTone }> = {
  available: { key: "users.status.available", tone: "neutral" },
  active_config: { key: "users.status.active_config", tone: "brand" },
  banned: { key: "users.status.banned", tone: "danger" },
};

const PAGE_SIZE = 25;

function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const meta = STATUS[status];
  return <Badge tone={meta?.tone ?? "neutral"}>{meta ? t(meta.key) : status}</Badge>;
}

export function Users() {
  const { t } = useI18n();
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
  const filters = [
    { value: "", label: t("users.filter.all") },
    { value: "available", label: t("users.status.available") },
    { value: "active_config", label: t("users.status.active_config") },
    { value: "banned", label: t("users.status.banned") },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("users.title")} sub={t("users.sub", { n: formatNumber(total) })}>
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-[240px] flex-1">
            <Input
              aria-label={t("users.searchAria")}
              icon={<Search className="h-4 w-4" />}
              placeholder={t("users.search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <Segmented
            value={status}
            onChange={setStatus}
            options={filters}
            size="sm"
            ariaLabel={t("users.filterAria")}
          />
        </div>
      </PageHeader>

      {/* Mounted only while a row is selected — the dialog's hooks (useConfirm, the detail query)
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
            title={t("users.empty.title")}
            message={search || status ? t("users.empty.filtered") : t("users.empty.none")}
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>{t("users.col.user")}</TH>
                <TH>{t("users.col.status")}</TH>
                <TH>{t("users.col.invites")}</TH>
                <TH>{t("users.col.panel")}</TH>
                <TH>{t("users.col.joined")}</TH>
              </TR>
            </THead>
            <TBody>
              {data.items.map((u) => (
                <TR
                  key={u.telegram_id}
                  onClick={() => setDetailId(u.telegram_id)}
                  selected={u.telegram_id === detailId}
                >
                  <TD>
                    <span className="flex items-center gap-2.5">
                      {/* Seeded on the id, not the username: the panel name can change and the
                          same person would swap colour mid-list. */}
                      <Avatar
                        name={u.panel_username ?? String(u.telegram_id)}
                        seed={String(u.telegram_id)}
                      />
                      <span className="font-mono text-sm" dir="ltr">
                        {u.telegram_id}
                      </span>
                    </span>
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
      {/* Isolated rather than forced LTR: `direction: ltr` on a block also drags the text to the
          left edge, away from the label it belongs to. */}
      <span className="text-content" style={{ unicodeBidi: "isolate" }}>
        {value}
      </span>
    </div>
  );
}

/** One headline figure with its own glyph — the three that answer "who is this" at a glance. */
function StatTile({
  icon: Icon,
  tone,
  value,
  label,
}: {
  icon: typeof Ticket;
  tone: string;
  value: ReactNode;
  label: string;
}) {
  return (
    <div className="flex flex-col gap-1.5 rounded-xl bg-surface-sunken p-3">
      <span className={`grid h-7 w-7 place-items-center rounded-lg ${tone}`}>
        <Icon className="h-3.5 w-3.5" />
      </span>
      <b className="text-lg font-bold leading-none tabular-nums text-content">{value}</b>
      <span className="text-[11px] text-content-subtle">{label}</span>
    </div>
  );
}

function UserDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const { t } = useI18n();
  const { data: user, isLoading } = useUser(id);
  const action = useUserAction();
  const confirm = useConfirm();

  async function run(name: UserAction, destructive = false) {
    if (
      destructive &&
      !(await confirm({
        message: t("users.action.confirm"),
        tone: "danger",
        confirmLabel: t("users.action.confirmLabel"),
      }))
    ) {
      return;
    }
    action.mutate(
      { id, action: name },
      {
        onSuccess: () => toast.success(t("users.action.done")),
        onError: () => toast.error(t("users.action.failed")),
      },
    );
  }

  return (
    <RecordDialog
      open
      onClose={onClose}
      title={
        <span className="flex items-center gap-2.5">
          <Avatar
            name={user?.panel_username ?? String(id)}
            seed={String(id)}
            className="h-9 w-9 text-xs"
          />
          {t("users.detail.title")}
        </span>
      }
      sub={String(id)}
      footer={
        user ? (
          <>
            {user.status === "banned" ? (
              <Button onClick={() => run("unban")} loading={action.isPending}>
                {t("users.action.unban")}
              </Button>
            ) : (
              <Button variant="danger" onClick={() => run("ban", true)} loading={action.isPending}>
                {t("users.action.ban")}
              </Button>
            )}
            <Button variant="outline" onClick={() => run("reclaim")} loading={action.isPending}>
              {t("users.action.reclaim")}
            </Button>
            <span className="flex-1" />
            <Button
              variant="ghost"
              onClick={() => run("zero_referrals", true)}
              loading={action.isPending}
            >
              {t("users.action.zeroReferrals")}
            </Button>
          </>
        ) : undefined
      }
    >
      {isLoading || !user ? (
        <div className="flex justify-center py-10">
          <Spinner className="h-6 w-6 text-brand" />
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-2">
            <StatTile
              icon={Ticket}
              tone="bg-chart-1/20 text-chart-1"
              value={formatNumber(user.configs ?? 0)}
              label={t("users.stat.claims")}
            />
            <StatTile
              icon={Gift}
              tone="bg-chart-3/20 text-chart-3"
              value={formatNumber(user.referral_count)}
              label={t("users.stat.invites")}
            />
            <StatTile
              icon={UserX}
              tone="bg-chart-4/20 text-chart-4"
              value={<span className="text-sm">{faDate(user.created_at)}</span>}
              label={t("users.stat.joined")}
            />
          </div>

          <div>
            <DetailRow
              label={t("users.detail.telegramId")}
              value={<span className="font-mono">{user.telegram_id}</span>}
            />
            <DetailRow label={t("users.col.status")} value={<StatusBadge status={user.status} />} />
            <DetailRow label={t("users.detail.language")} value={langLabel(user.language)} />
            <DetailRow label={t("users.col.panel")} value={user.panel_username ?? "—"} />
            <DetailRow label={t("users.detail.referredBy")} value={user.referred_by ?? "—"} />
          </div>
        </div>
      )}
    </RecordDialog>
  );
}
