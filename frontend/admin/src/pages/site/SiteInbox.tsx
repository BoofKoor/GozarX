import { clsx } from "clsx";
import { ChevronLeft, ChevronRight, Mail, MailOpen } from "lucide-react";
import { useEffect, useState } from "react";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import { useMarkMessageRead, useSiteMessages } from "@/hooks/useSite";
import type { SiteMessage } from "@/types/api";

function fmtDate(s: string | null): string {
  return s ? new Date(s).toLocaleString("fa-IR") : "";
}

export function SiteInbox() {
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data, isLoading, isError, refetch } = useSiteMessages(page, unreadOnly);
  const markRead = useMarkMessageRead();

  const items = data?.items ?? [];
  const selected = items.find((m) => m.id === selectedId) ?? null;
  // Page by the count that matches the active filter: `total` counts ALL messages, but in
  // unread-only mode the list is the (smaller) `unread` set — using `total` would show phantom
  // empty pages past the real end.
  const totalCount = unreadOnly ? (data?.unread ?? 0) : (data?.total ?? 0);
  const totalPages = data ? Math.max(1, Math.ceil(totalCount / data.page_size)) : 1;

  // Reading in unread-only mode shrinks the list; if the current page falls past the end, step back.
  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
      setSelectedId(null);
    }
  }, [totalPages, page]);

  function reset(nextUnread: boolean) {
    setUnreadOnly(nextUnread);
    setPage(1);
    setSelectedId(null);
  }

  function open(m: SiteMessage) {
    setSelectedId(m.id);
    if (!m.read) markRead.mutate(m.id);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">وب‌سایت</h1>
      <SiteTabs />

      <div className="flex items-center gap-3 text-sm">
        <span className="text-slate-500">
          خوانده‌نشده:{" "}
          <span className="font-bold text-brand">{data?.unread ?? (isError ? "—" : "…")}</span>
        </span>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => reset(e.target.checked)}
            className="h-4 w-4 accent-brand"
          />
          فقط خوانده‌نشده‌ها
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          {isError && !data ? (
            <ErrorState compact onRetry={() => refetch()} />
          ) : isLoading ? (
            <div className="flex justify-center py-10">
              <Spinner className="h-6 w-6 text-brand" />
            </div>
          ) : items.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-400">پیامی نیست.</p>
          ) : (
            <ul className="max-h-[60vh] space-y-1 overflow-y-auto">
              {items.map((m) => (
                <li key={m.id}>
                  <button
                    onClick={() => open(m)}
                    className={clsx(
                      "flex w-full items-start gap-2 rounded-lg px-2 py-2 text-right text-sm transition",
                      m.id === selectedId
                        ? "bg-brand/10 text-brand"
                        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
                    )}
                  >
                    {m.read ? (
                      <MailOpen className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                    ) : (
                      <Mail className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className={clsx("block truncate", !m.read && "font-bold")} dir="auto">
                        {m.subject}
                      </span>
                      <span className="block truncate text-xs text-slate-400">
                        {fmtDate(m.created_at)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {data && totalCount > data.page_size && (
            <div className="mt-3 flex items-center justify-between text-sm">
              <Button
                variant="ghost"
                size="sm"
                aria-label="صفحهٔ قبل"
                disabled={page <= 1}
                onClick={() => {
                  setPage((p) => p - 1);
                  setSelectedId(null);
                }}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
              <span className="text-slate-400">
                {page} / {totalPages}
              </span>
              <Button
                variant="ghost"
                size="sm"
                aria-label="صفحهٔ بعد"
                disabled={page >= totalPages}
                onClick={() => {
                  setPage((p) => p + 1);
                  setSelectedId(null);
                }}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
            </div>
          )}
        </Card>

        <div className="lg:col-span-2">
          {selected ? (
            <Card className="space-y-3">
              <h2 className="text-lg font-bold" dir="auto">
                {selected.subject}
              </h2>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                <span>{fmtDate(selected.created_at)}</span>
                <span>زبان: {selected.locale}</span>
                {selected.reply_handle && <span dir="auto">راه پاسخ: {selected.reply_handle}</span>}
              </div>
              {/* User-submitted text — render as PLAIN text (never HTML). */}
              <div
                className="whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm dark:border-slate-700 dark:bg-slate-800"
                dir="auto"
              >
                {selected.body}
              </div>
            </Card>
          ) : (
            <Card className="flex h-64 items-center justify-center text-slate-400">
              <div className="text-center">
                <Mail className="mx-auto mb-2 h-8 w-8" />
                یک پیام را برای خواندن انتخاب کنید
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
