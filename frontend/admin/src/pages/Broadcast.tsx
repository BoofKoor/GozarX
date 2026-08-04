import { clsx } from "clsx";
import { Check, Clock, Send, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { HourStrip } from "@/components/charts/HourStrip";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { useConfirm } from "@/components/ui/confirm";
import { useAudience, useSendBroadcast } from "@/hooks/useBroadcast";
import { useDashboardAnalytics } from "@/hooks/useDashboard";
import { useSystemHealth } from "@/hooks/useSystem";
import { useI18n } from "@/i18n";
import {
  formatNumber,
  joinList,
  langLabel,
  localizeDigits,
  telegramPreviewHtml,
} from "@/lib/format";
import type { Lang } from "@/types/api";

const ALL_LANGS: Lang[] = ["fa", "en", "ru"];
/** Telegram's own message ceiling — not a house style choice. */
const MAX_CHARS = 4096;
/** The practical broadcast ceiling the worker paces itself to stay under. */
const RATE_PER_SEC = 30;
const TONES = ["bg-chart-1", "bg-chart-3", "bg-chart-4"];

/** One pre-flight line. Each is a condition the send genuinely depends on. */
function PreflightRow({ ok, children }: { ok: boolean; children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 text-[13px] leading-relaxed">
      <span
        className={clsx(
          "mt-0.5 grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full",
          ok ? "bg-success-500/20 text-success-700" : "bg-danger-500/20 text-danger-700",
        )}
      >
        {ok ? <Check className="h-2.5 w-2.5" /> : <X className="h-2.5 w-2.5" />}
      </span>
      <span className={ok ? "text-content-muted" : "font-semibold text-danger-700"}>
        {children}
      </span>
    </div>
  );
}

export function Broadcast() {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [langs, setLangs] = useState<Lang[]>(ALL_LANGS);

  const { data: audience, isError: audienceError } = useAudience(langs);
  const { data: everyone } = useAudience(ALL_LANGS);
  // One cheap COUNT per language gives the reach bar a real breakdown, using only the endpoint the
  // page already has. Inventing the split was the alternative.
  const perLang = [useAudience(["fa"]), useAudience(["en"]), useAudience(["ru"])];
  const { data: analytics } = useDashboardAnalytics(30);
  const { data: health } = useSystemHealth();
  const send = useSendBroadcast();
  const confirm = useConfirm();

  const total = everyone?.recipients ?? 0;
  // No language selected means nobody. The backend reads an empty list as EVERYONE, so the send is
  // blocked here rather than allowed to mean its opposite.
  const recipients = langs.length ? (audience?.recipients ?? 0) : 0;
  const allSelected = langs.length === ALL_LANGS.length;
  const summary = allSelected ? t("bc.langs.all") : joinList(langs.map(langLabel));

  const body = text.trim();
  const overLimit = text.length > MAX_CHARS;
  // The broadcast is queued in Redis for the arq worker; if Redis is down it cannot be queued at
  // all, which is worth knowing BEFORE composing rather than after pressing send.
  const queueOk = health?.redis.ok !== false;
  const canSend = Boolean(body) && langs.length > 0 && !overLimit && queueOk;
  const minutes = Math.max(1, Math.round(recipients / RATE_PER_SEC / 60));

  const byHour = (() => {
    const acc: number[] = new Array(24).fill(0);
    for (const cell of analytics?.heatmap ?? []) acc[cell.hour] += cell.count;
    return acc;
  })();
  const peakHour = byHour.some((n) => n > 0) ? byHour.indexOf(Math.max(...byHour)) : -1;

  function toggle(code: Lang) {
    setLangs((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  }

  async function submit() {
    if (!canSend) return;
    const ok = await confirm({
      title: t("bc.send.confirmTitle"),
      message: t("bc.send.confirm", { n: formatNumber(recipients), who: summary }),
      confirmLabel: t("bc.send"),
    });
    if (!ok) return;
    send.mutate(
      { text: body, languages: langs },
      {
        onSuccess: (r) => {
          toast.success(t("bc.send.queued", { n: formatNumber(r.recipients), who: summary }));
          setText("");
        },
        onError: () => toast.error(t("bc.send.failed")),
      },
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t("bc.title")} sub={t("bc.sub")} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <Card className="space-y-3">
            <h3 className="text-sm font-bold text-content">{t("bc.audience")}</h3>
            <div className="flex flex-wrap gap-2">
              {ALL_LANGS.map((code) => {
                const on = langs.includes(code);
                return (
                  <button
                    key={code}
                    type="button"
                    onClick={() => toggle(code)}
                    aria-pressed={on}
                    className={clsx(
                      "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium transition",
                      on
                        ? "border-brand bg-brand/20 text-brand-700"
                        : "border-line text-content-muted hover:border-line-strong hover:text-content",
                    )}
                  >
                    {/* A tint alone is a weak signal for a state that decides who gets the message;
                        the tick says "on" at any contrast. */}
                    <Check className={clsx("h-3.5 w-3.5", !on && "invisible")} />
                    {langLabel(code)}
                  </button>
                );
              })}
            </div>

            {/* The count says how many; the bar says how many OF WHAT — which is the question you
                actually have before pressing send. */}
            <div className="flex h-2 overflow-hidden rounded-full bg-surface-sunken">
              {ALL_LANGS.map((code, i) =>
                langs.includes(code) && total > 0 ? (
                  <span
                    key={code}
                    className={TONES[i]}
                    style={{ width: `${((perLang[i].data?.recipients ?? 0) / total) * 100}%` }}
                  />
                ) : null,
              )}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-content-subtle">
              {ALL_LANGS.map((code, i) => (
                <span
                  key={code}
                  // Dimmed when deselected, so the legend answers "who is in this bar", not just
                  // "what colour is each language".
                  className={clsx(
                    "inline-flex items-center gap-1.5",
                    !langs.includes(code) && "opacity-40",
                  )}
                >
                  <i className={clsx("h-2 w-2 rounded-sm", TONES[i])} aria-hidden />
                  {langLabel(code)} {formatNumber(perLang[i].data?.recipients ?? 0)}
                </span>
              ))}
            </div>
            <p className="text-xs text-content-muted">
              {audienceError
                ? t("bc.audience.unreachable")
                : t("bc.audience.hint", {
                    n: formatNumber(recipients),
                    total: formatNumber(total),
                  })}
            </p>
            {langs.length === 0 && (
              <p className="text-xs font-medium text-danger-700">{t("bc.audience.empty")}</p>
            )}
          </Card>

          <Card className="space-y-3">
            <h3 className="text-sm font-bold text-content">{t("bc.compose")}</h3>
            <div>
              <div className="flex items-center gap-2 rounded-t-xl border border-b-0 border-line bg-surface-sunken px-2.5 py-1.5">
                <span className="flex-1 text-xs text-content-subtle">{t("bc.text")}</span>
                {/* `dir` and not just an isolate: two numbers around a slash swap places under an
                    RTL base direction, so «۱۳۸ / ۴٬۰۹۶» rendered as «۴٬۰۹۶ / ۱۳۸» — the message
                    reading as longer than the limit. Safe on an inline run; never on a block. */}
                <span
                  dir="ltr"
                  className={clsx(
                    "text-xs tabular-nums",
                    overLimit ? "font-bold text-danger-700" : "text-content-subtle",
                  )}
                >
                  {formatNumber(text.length)} / {formatNumber(MAX_CHARS)}
                </span>
              </div>
              <textarea
                className="field-control min-h-[180px] rounded-t-none"
                placeholder={t("bc.text.placeholder")}
                value={text}
                onChange={(e) => setText(e.target.value)}
                dir="auto"
              />
            </div>
            <p className="text-xs text-content-subtle">{t("bc.text.hint")}</p>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button onClick={submit} loading={send.isPending} disabled={!canSend}>
                <Send className="h-4 w-4" />
                {t("bc.send")}
              </Button>
              <span className="flex-1" />
              <span className="inline-flex items-center gap-1.5 text-xs text-content-muted">
                <Clock className="h-3.5 w-3.5 text-content-subtle" />
                {t("bc.eta", { m: formatNumber(minutes), rate: formatNumber(RATE_PER_SEC) })}
              </span>
            </div>
          </Card>

          <Card className="space-y-2">
            <h3 className="text-sm font-bold text-content">{t("bc.timing")}</h3>
            <HourStrip counts={byHour} mark={peakHour >= 0 ? peakHour : undefined} />
            <p className="text-xs text-content-subtle">
              {peakHour < 0
                ? t("bc.timing.noData")
                : t("bc.timing.hint", {
                    h: localizeDigits(`${String(peakHour).padStart(2, "0")}:00`),
                  })}
            </p>
          </Card>
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          <Card className="space-y-3">
            <h3 className="text-sm font-bold text-content">{t("bc.preview")}</h3>
            {/* A chat frame rather than a lone bubble: half of what lands in Telegram is the header
                and the timestamp around it. */}
            <div className="overflow-hidden rounded-xl border border-line bg-surface-sunken">
              <div className="flex items-center gap-2 border-b border-line bg-surface-hover px-2.5 py-2">
                <span className="grid h-7 w-7 place-items-center rounded-full bg-brand text-[10px] font-bold text-white">
                  GX
                </span>
                <span className="min-w-0">
                  <b className="block text-xs font-semibold text-content">GozarX</b>
                  <span className="block text-[10px] text-content-subtle">
                    {t("bc.preview.bot", { n: formatNumber(total) })}
                  </span>
                </span>
              </div>
              <div className="p-2.5">
                {body ? (
                  <div
                    // Sanitised: the panel origin holds the JWTs, so pasted markup must never
                    // execute here even though an admin typed it.
                    className="whitespace-pre-wrap rounded-xl bg-surface-hover px-3 py-2 text-[13px] leading-7"
                    dir="auto"
                    dangerouslySetInnerHTML={{ __html: telegramPreviewHtml(text) }}
                  />
                ) : (
                  <p className="py-4 text-center text-xs text-content-subtle">
                    {t("bc.preview.empty")}
                  </p>
                )}
              </div>
            </div>
          </Card>

          <Card className="space-y-2.5">
            <h3 className="text-sm font-bold text-content">{t("bc.preflight")}</h3>
            <PreflightRow ok={langs.length > 0}>
              {langs.length > 0 ? t("bc.pf.audience") : t("bc.pf.audienceBad")}
            </PreflightRow>
            <PreflightRow ok={Boolean(body)}>
              {body ? t("bc.pf.text") : t("bc.pf.textBad")}
            </PreflightRow>
            <PreflightRow ok={!overLimit}>
              {overLimit
                ? t("bc.pf.lengthBad", { max: formatNumber(MAX_CHARS) })
                : t("bc.pf.length")}
            </PreflightRow>
            <PreflightRow ok={queueOk}>
              {queueOk ? t("bc.pf.queue") : t("bc.pf.queueBad")}
            </PreflightRow>
          </Card>
        </div>
      </div>
    </div>
  );
}
