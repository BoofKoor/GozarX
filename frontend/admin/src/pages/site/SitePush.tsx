import { clsx } from "clsx";
import { BellRing, History, Send, Users as UsersIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Segmented } from "@/components/ui/Segmented";
import { Textarea } from "@/components/ui/Textarea";
import { useConfirm } from "@/components/ui/confirm";
import { useSendSitePush, useSitePushAudience, useSitePushHistory } from "@/hooks/useSite";
import { useI18n, type MessageKey } from "@/i18n";
import { apiErrorMessage } from "@/lib/api";
import { faDate, formatNumber, langLabel } from "@/lib/format";
import type { SitePushLog } from "@/types/api";

const STATUS: Record<string, { label: MessageKey; tone: BadgeTone }> = {
  queued: { label: "sp.status.queued", tone: "neutral" },
  sending: { label: "sp.status.sending", tone: "info" },
  done: { label: "sp.status.done", tone: "success" },
  failed: { label: "sp.status.failed", tone: "danger" },
};

export function SitePush() {
  const { t } = useI18n();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [url, setUrl] = useState("");
  const [locale, setLocale] = useState<string>("");
  const { data: audience, isError: audienceError } = useSitePushAudience();
  const { data: history = [] } = useSitePushHistory();
  const send = useSendSitePush();
  const confirm = useConfirm();

  // Targeting options are built from the audience the panel already reports, so the operator can
  // only pick a language that actually has subscribers.
  const localeOptions = [
    { value: "", label: t("sp.audience.all", { n: formatNumber(audience?.recipients ?? 0) }) },
    ...(audience?.by_locale ?? []).map((l) => ({
      value: l.locale,
      label: `${langLabel(l.locale)} (${formatNumber(l.count)})`,
    })),
  ];
  const reach = locale
    ? (audience?.by_locale.find((l) => l.locale === locale)?.count ?? 0)
    : (audience?.recipients ?? 0);

  async function submit() {
    const headline = title.trim();
    const b = body.trim();
    if (!headline || !b) return;
    const ok = await confirm({
      title: t("sp.send.title"),
      message: t("sp.send.confirm", { n: formatNumber(reach) }),
      confirmLabel: t("sp.send.label"),
    });
    if (!ok) return;
    send.mutate(
      { title: headline, body: b, url: url.trim(), locale: locale || null },
      {
        onSuccess: (r) => {
          toast.success(t("sp.send.queued", { n: formatNumber(r.recipients) }));
          setTitle("");
          setBody("");
          setUrl("");
        },
        // 422 (bad link), 409 (nobody subscribed) and 503 (worker down) are very different
        // problems; show the server's own words instead of one generic failure.
        onError: (err) => toast.error(apiErrorMessage(err, t("sp.send.failed"))),
      },
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t("sp.title")} sub={t("sp.sub")}>
        <SiteTabs />
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="space-y-4 lg:col-span-3">
          <CardHeader
            title={t("sp.new")}
            icon={BellRing}
            action={
              <span className="flex items-center gap-1.5 text-xs text-content-muted">
                <UsersIcon className="h-3.5 w-3.5" />
                {audienceError ? "—" : t("sp.reach", { n: formatNumber(reach) })}
              </span>
            }
          />
          <Field label={t("sp.audience")} hint={t("sp.audience.hint")}>
            <Segmented
              value={locale}
              onChange={setLocale}
              options={localeOptions}
              size="sm"
              ariaLabel={t("sp.audience.aria")}
            />
          </Field>
          <Field label={t("sp.headline")}>
            <Input
              dir="auto"
              maxLength={120}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </Field>
          <Field label={t("sp.body")}>
            <Textarea
              dir="auto"
              maxLength={300}
              className="min-h-[120px]"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </Field>
          <Field label={t("sp.url")} hint={t("sp.url.hint")}>
            <Input
              dir="ltr"
              maxLength={512}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="/status"
            />
          </Field>

          <PushPreview title={title} body={body} />

          <div className="flex items-center justify-between gap-2">
            <p className="text-xs text-content-subtle">{t("sp.worker")}</p>
            <Button
              onClick={submit}
              loading={send.isPending}
              disabled={!title.trim() || !body.trim()}
            >
              <Send className="h-4 w-4" /> {t("sp.send")}
            </Button>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title={t("sp.history")} sub={t("sp.history.sub")} icon={History} />
          {history.length === 0 ? (
            <EmptyState title={t("sp.history.empty")} />
          ) : (
            <ul className="space-y-2">
              {history.map((row) => (
                <PushHistoryRow key={row.id} row={row} />
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

/** What the notification will actually look like — the box used to be write-only. */
function PushPreview({ title, body }: { title: string; body: string }) {
  const { t } = useI18n();
  if (!title.trim() && !body.trim()) return null;
  return (
    <div>
      <div className="mb-1.5 text-xs font-medium text-content-muted">{t("sp.preview")}</div>
      <div className="flex gap-3 rounded-xl border border-line bg-surface-raised p-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand text-white">
          <BellRing className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-content" dir="auto">
            {title.trim() || t("sp.headline")}
          </div>
          <div className="line-clamp-2 text-xs text-content-muted" dir="auto">
            {body.trim() || t("sp.body")}
          </div>
        </div>
      </div>
    </div>
  );
}

function PushHistoryRow({ row }: { row: SitePushLog }) {
  const { t } = useI18n();
  const meta = STATUS[row.status];
  const delivered = row.recipients > 0 ? (row.sent / row.recipients) * 100 : 0;
  return (
    <li className="rounded-xl border border-line p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-content" dir="auto">
            {row.title}
          </div>
          <div className="mt-0.5 text-xs text-content-subtle">
            {faDate(row.created_at)}
            {row.locale && ` · ${langLabel(row.locale)}`}
          </div>
        </div>
        <Badge tone={meta?.tone ?? "neutral"} dot={row.status === "sending"}>
          {meta ? t(meta.label) : row.status}
        </Badge>
      </div>
      {row.status === "done" && (
        <>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-sunken">
            <div
              className={clsx(
                "h-full rounded-full",
                delivered > 80 ? "bg-success-500" : "bg-warning-500",
              )}
              style={{ width: `${delivered}%` }}
            />
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-3 text-[11px] tabular-nums text-content-muted">
            <span>{t("sp.stat.sent", { n: formatNumber(row.sent) })}</span>
            {row.failed > 0 && <span>{t("sp.stat.failed", { n: formatNumber(row.failed) })}</span>}
            {row.pruned > 0 && <span>{t("sp.stat.pruned", { n: formatNumber(row.pruned) })}</span>}
            <span>{t("sp.stat.of", { n: formatNumber(row.recipients) })}</span>
          </div>
        </>
      )}
    </li>
  );
}
