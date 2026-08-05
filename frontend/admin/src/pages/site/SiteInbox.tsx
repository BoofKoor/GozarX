import { clsx } from "clsx";
import { ExternalLink, Mail, MailOpen, Search, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox } from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Segmented } from "@/components/ui/Segmented";
import { Spinner } from "@/components/ui/Spinner";
import { useConfirm } from "@/components/ui/confirm";
import {
  useDeleteMessage,
  useMarkMessageRead,
  useMarkMessageUnread,
  useSiteMessages,
} from "@/hooks/useSite";
import { useI18n } from "@/i18n";
import { apiErrorMessage } from "@/lib/api";
import { faDateTime, formatNumber, langLabel } from "@/lib/format";
import type { SiteMessage } from "@/types/api";

function fmtDate(s: string | null): string {
  return s ? faDateTime(s) : "";
}

/**
 * Turn a visitor-supplied reply handle into a link when it is recognisably one.
 *
 * The field is free text on the public form, so it is ATTACKER-supplied: only an email address or a
 * plain @telegram username becomes a link, and everything else stays inert text. Never trust it
 * enough to build an arbitrary href.
 */
function replyLink(handle: string): { href: string; label: string } | null {
  const value = handle.trim();
  if (/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value)) {
    return { href: `mailto:${value}`, label: value };
  }
  const tg = value.replace(/^@/, "");
  if (/^[A-Za-z0-9_]{5,32}$/.test(tg) && value.startsWith("@")) {
    return { href: `https://t.me/${tg}`, label: value };
  }
  return null;
}

export function SiteInbox() {
  const { t } = useI18n();
  const LOCALES = [
    { value: "", label: t("si.locale.all") },
    { value: "fa", label: langLabel("fa") },
    { value: "en", label: langLabel("en") },
  ];
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [search, setSearch] = useState("");
  const [locale, setLocale] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data, isLoading, isError, refetch } = useSiteMessages(page, unreadOnly, search, locale);
  const markRead = useMarkMessageRead();

  const items = data?.items ?? [];
  const selected = items.find((m) => m.id === selectedId) ?? null;
  // Page by the count that matches the ACTIVE filter — `total` counts every message, so with a
  // search or unread-only on it would show phantom empty pages past the real end.
  const totalPages = data ? Math.max(1, Math.ceil(data.matching / data.page_size)) : 1;

  // Reading in unread-only mode shrinks the list; if the current page falls past the end, step back.
  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
      setSelectedId(null);
    }
  }, [totalPages, page]);

  useEffect(() => {
    setPage(1);
    setSelectedId(null);
  }, [unreadOnly, search, locale]);

  function open(m: SiteMessage) {
    setSelectedId(m.id);
    if (!m.read) markRead.mutate(m.id);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("si.title")}
        sub={t("si.sub")}
        actions={
          data && data.unread > 0 ? (
            <Badge tone="brand">{t("si.unread", { n: formatNumber(data.unread) })}</Badge>
          ) : undefined
        }
      >
        <SiteTabs unreadMessages={data?.unread} />
      </PageHeader>

      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[220px] flex-1">
          <Input
            aria-label={t("si.searchAria")}
            icon={<Search className="h-4 w-4" />}
            placeholder={t("si.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Segmented
          value={locale}
          onChange={setLocale}
          options={LOCALES}
          size="sm"
          ariaLabel={t("si.localeAria")}
        />
        <Checkbox checked={unreadOnly} onChange={setUnreadOnly} label={t("si.unreadOnly")} />
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
            <EmptyState
              icon={Mail}
              title={t("si.empty")}
              message={search || unreadOnly || locale ? t("si.empty.filtered") : undefined}
            />
          ) : (
            <ul className="scrollbar-thin max-h-[60vh] space-y-1 overflow-y-auto">
              {items.map((m) => (
                <li key={m.id}>
                  <button
                    onClick={() => open(m)}
                    className={clsx(
                      "flex w-full items-start gap-2 rounded-lg px-2 py-2 text-start text-sm transition",
                      m.id === selectedId
                        ? "bg-brand/10 text-brand-700"
                        : "text-content-muted hover:bg-surface-hover",
                    )}
                  >
                    {m.read ? (
                      <MailOpen className="mt-0.5 h-4 w-4 shrink-0 text-content-subtle" />
                    ) : (
                      <Mail className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className={clsx("block truncate", !m.read && "font-bold")} dir="auto">
                        {m.subject}
                      </span>
                      <span className="block truncate text-xs text-content-subtle">
                        {fmtDate(m.created_at)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Pagination page={page} totalPages={totalPages} onChange={setPage} className="mt-3" />
        </Card>

        <div className="lg:col-span-2">
          {selected ? (
            <MessageView
              message={selected}
              onDeleted={() => setSelectedId(null)}
              onUnread={() => setSelectedId(null)}
            />
          ) : (
            <Card>
              <EmptyState icon={Mail} title={t("si.pick")} />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function MessageView({
  message,
  onDeleted,
  onUnread,
}: {
  message: SiteMessage;
  onDeleted: () => void;
  onUnread: () => void;
}) {
  const { t } = useI18n();
  const markUnread = useMarkMessageUnread();
  const del = useDeleteMessage();
  const confirm = useConfirm();
  const reply = message.reply_handle ? replyLink(message.reply_handle) : null;

  async function remove() {
    const ok = await confirm({
      title: t("si.delete.title"),
      message: t("si.delete.confirm"),
      tone: "danger",
      confirmLabel: t("si.delete.label"),
    });
    if (!ok) return;
    del.mutate(message.id, {
      onSuccess: () => {
        toast.success(t("si.deleted"));
        onDeleted();
      },
      onError: (err) => toast.error(apiErrorMessage(err, t("si.deleteFailed"))),
    });
  }

  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="text-lg font-bold text-content" dir="auto">
          {message.subject}
        </h2>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            loading={markUnread.isPending}
            onClick={() =>
              markUnread.mutate(message.id, {
                onSuccess: () => {
                  toast.success(t("si.markedUnread"));
                  onUnread();
                },
              })
            }
          >
            <Mail className="h-4 w-4" />
            {t("si.markUnread")}
          </Button>
          <Button variant="ghost" size="sm" onClick={remove} loading={del.isPending}>
            <Trash2 className="h-4 w-4 text-danger-600" />
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-content-subtle">
        <span>{fmtDate(message.created_at)}</span>
        <span>{t("si.language", { lang: langLabel(message.locale) })}</span>
        {message.device_uuid && (
          <Link
            to={`/site/devices?search=${encodeURIComponent(message.device_uuid)}`}
            className="inline-flex items-center gap-1 text-brand hover:underline"
          >
            {t("si.senderDevice")}
            <ExternalLink className="h-3 w-3" />
          </Link>
        )}
      </div>

      {message.reply_handle && (
        <div className="flex items-center gap-2 rounded-xl bg-surface-raised px-3 py-2 text-sm">
          <span className="text-content-muted">{t("si.replyVia")}</span>
          {reply ? (
            <a
              href={reply.href}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-brand hover:underline"
              dir="ltr"
            >
              {reply.label}
              <ExternalLink className="h-3 w-3" />
            </a>
          ) : (
            // Unrecognised shapes stay inert text — the field is visitor-supplied.
            <span dir="auto" className="text-content">
              {message.reply_handle}
            </span>
          )}
        </div>
      )}

      {/* User-submitted text — render as PLAIN text (never HTML). */}
      <div
        className="whitespace-pre-wrap rounded-xl border border-line bg-surface-sunken p-3 text-sm text-content"
        dir="auto"
      >
        {message.body}
      </div>
    </Card>
  );
}
