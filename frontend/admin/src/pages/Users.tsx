import { clsx } from "clsx";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { type ReactNode, useDeferredValue, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Modal } from "@/components/ui/Modal";
import { Spinner } from "@/components/ui/Spinner";
import { useUser, useUserAction, useUsers } from "@/hooks/useUsers";
import type { UserAction } from "@/types/api";

const STATUS: Record<string, { label: string; cls: string }> = {
  available: { label: "در دسترس", cls: "bg-slate-100 text-slate-600 dark:bg-slate-800" },
  active_config: {
    label: "فعال",
    cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  },
  banned: {
    label: "مسدود",
    cls: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
  },
};

const FILTERS: { value: string; label: string }[] = [
  { value: "", label: "همه" },
  { value: "available", label: "در دسترس" },
  { value: "active_config", label: "فعال" },
  { value: "banned", label: "مسدود" },
];

const PAGE_SIZE = 25;

function StatusBadge({ status }: { status: string }) {
  const meta = STATUS[status] ?? { label: status, cls: "bg-slate-100 text-slate-600" };
  return <span className={clsx("rounded px-1.5 py-0.5 text-xs", meta.cls)}>{meta.label}</span>;
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
      <h1 className="text-xl font-bold">کاربران</h1>

      {detailId != null && <UserDetail id={detailId} onClose={() => setDetailId(null)} />}

      <Card className="space-y-3">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            aria-label="جستجوی کاربران"
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 pr-9 text-sm outline-none focus:border-brand dark:border-slate-700 dark:bg-slate-900"
            placeholder="جستجو با آیدی تلگرام یا یوزرنیم پنل…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatus(f.value)}
              className={clsx(
                "rounded-full px-3 py-1 text-xs transition",
                status === f.value
                  ? "bg-brand text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </Card>

      <Card>
        {isError && !data ? (
          <ErrorState compact onRetry={() => refetch()} />
        ) : isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner className="h-7 w-7 text-brand" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="py-12 text-center text-sm text-slate-400">کاربری یافت نشد</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs text-slate-400">
                <tr className="border-b border-slate-100 dark:border-slate-800">
                  <th className="p-2 text-right font-medium">آیدی تلگرام</th>
                  <th className="p-2 text-right font-medium">وضعیت</th>
                  <th className="p-2 text-right font-medium">دعوت‌ها</th>
                  <th className="p-2 text-right font-medium">یوزرنیم پنل</th>
                  <th className="p-2 text-right font-medium">عضویت</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((u) => (
                  <tr
                    key={u.telegram_id}
                    onClick={() => setDetailId(u.telegram_id)}
                    className="cursor-pointer border-b border-slate-50 transition hover:bg-slate-50 dark:border-slate-800/50 dark:hover:bg-slate-800/50"
                  >
                    <td className="p-2 font-mono" dir="ltr">
                      {u.telegram_id}
                    </td>
                    <td className="p-2">
                      <StatusBadge status={u.status} />
                    </td>
                    <td className="p-2">{u.referral_count}</td>
                    <td className="p-2 font-mono text-xs text-slate-500" dir="ltr">
                      {u.panel_username ?? "—"}
                    </td>
                    <td className="p-2 text-xs text-slate-500" dir="ltr">
                      {u.created_at ? u.created_at.slice(0, 10) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-3 flex items-center justify-between text-sm text-slate-500">
          <span>
            {total} کاربر · صفحه {page}/{pages}
          </span>
          <div className="flex gap-1">
            <button
              aria-label="صفحهٔ قبل"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-lg p-1.5 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
            <button
              aria-label="صفحهٔ بعد"
              disabled={page >= pages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-lg p-1.5 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-2 border-b border-slate-100 py-1.5 dark:border-slate-800">
      <span className="text-slate-500">{label}</span>
      <span dir="ltr">{value}</span>
    </div>
  );
}

function UserDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const { data: user, isLoading } = useUser(id);
  const action = useUserAction();

  function run(name: UserAction, destructive = false) {
    if (destructive && !window.confirm("از انجام این عمل مطمئنی؟")) return;
    action.mutate(
      { id, action: name },
      { onSuccess: () => toast.success("انجام شد."), onError: () => toast.error("ناموفق بود.") },
    );
  }

  return (
    <Modal onClose={onClose} className="max-w-md p-5" labelledBy="user-card-title">
      <h2 id="user-card-title" className="mb-3 text-lg font-bold">
        کارت کاربر
      </h2>
      {isLoading || !user ? (
        <div className="flex justify-center py-8">
          <Spinner className="h-6 w-6 text-brand" />
        </div>
      ) : (
        <>
          <div className="space-y-0 text-sm">
            <Field
              label="آیدی تلگرام"
              value={<span className="font-mono">{user.telegram_id}</span>}
            />
            <Field label="وضعیت" value={<StatusBadge status={user.status} />} />
            <Field label="زبان" value={user.language} />
            <Field label="دعوت‌ها" value={user.referral_count} />
            <Field label="کانفیگ‌های گرفته‌شده" value={user.configs ?? 0} />
            <Field label="یوزرنیم پنل" value={user.panel_username ?? "—"} />
            <Field label="معرف" value={user.referred_by ?? "—"} />
            <Field label="عضویت" value={user.created_at ? user.created_at.slice(0, 10) : "—"} />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {user.status === "banned" ? (
              <Button onClick={() => run("unban")} loading={action.isPending}>
                رفع مسدودی
              </Button>
            ) : (
              <Button onClick={() => run("ban", true)} loading={action.isPending}>
                مسدودسازی
              </Button>
            )}
            <Button variant="ghost" onClick={() => run("reclaim")} loading={action.isPending}>
              اجازهٔ دریافت مجدد
            </Button>
            <Button
              variant="ghost"
              onClick={() => run("zero_referrals", true)}
              loading={action.isPending}
            >
              صفر کردن دعوت‌ها
            </Button>
          </div>
        </>
      )}
      <div className="mt-4 flex justify-end">
        <Button variant="ghost" onClick={onClose}>
          بستن
        </Button>
      </div>
    </Modal>
  );
}
