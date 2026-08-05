import { clsx } from "clsx";
import { Check, Clock, Save, Send, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { KeyboardBuilder, MAX_CHARS, MessageField } from "@/components/broadcast/Composer";
import { DraftList } from "@/components/broadcast/DraftList";
import { BroadcastHistory } from "@/components/broadcast/History";
import { HourStrip } from "@/components/charts/HourStrip";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Switch } from "@/components/ui/Switch";
import { useConfirm } from "@/components/ui/confirm";
import {
  useAudience,
  useDeleteDraft,
  useDrafts,
  useSaveDraft,
  useSendBroadcast,
} from "@/hooks/useBroadcast";
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
import type { BroadcastButton, BroadcastDraft, Lang } from "@/types/api";

const ALL_LANGS: Lang[] = ["fa", "en", "ru"];
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

/** A filter chip: tint, border and weight all shift together, so "on" survives low contrast. */
function Chip({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={clsx(
        // No check glyph: `aria-pressed` already tells a screen reader, and the fill already tells
        // everyone else. Rendered `invisible` when off it still reserved its width, so every chip
        // carried a permanent 14px hole and the row read as a set of dropdowns rather than toggles.
        "inline-flex items-center rounded-full border px-[0.72rem] py-[0.3rem] text-[0.78rem] transition",
        on
          ? "border-brand/50 bg-brand/20 font-semibold text-brand"
          : "border-line font-medium text-content-muted hover:border-line-strong hover:text-content",
      )}
    >
      {children}
    </button>
  );
}

/** The next occurrence of a given hour, as an ISO instant. */
function nextOccurrence(hour: number): Date {
  const at = new Date();
  at.setMinutes(0, 0, 0);
  at.setHours(hour);
  if (at.getTime() <= Date.now()) at.setDate(at.getDate() + 1);
  return at;
}

export function Broadcast() {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [langs, setLangs] = useState<Lang[]>(ALL_LANGS);
  const [onlyActive, setOnlyActive] = useState(false);
  const [onlyReferrers, setOnlyReferrers] = useState(false);
  const [buttons, setButtons] = useState<BroadcastButton[]>([]);
  const [scheduled, setScheduled] = useState(false);
  const [hour, setHour] = useState<number | null>(null);
  // Which saved draft the composer is currently holding, so saving again overwrites it rather
  // than leaving a trail of near-identical copies behind every edit.
  const [draftId, setDraftId] = useState<number | null>(null);

  const filter = { only_active: onlyActive, only_referrers: onlyReferrers };
  const { data: audience, isError: audienceError } = useAudience(langs, filter);
  const { data: everyone } = useAudience(ALL_LANGS);
  // One cheap COUNT per language gives the reach bar a real breakdown, using only the endpoint the
  // page already has. Inventing the split was the alternative.
  const perLang = [
    useAudience(["fa"], filter),
    useAudience(["en"], filter),
    useAudience(["ru"], filter),
  ];
  const { data: analytics } = useDashboardAnalytics(30);
  const { data: health } = useSystemHealth();
  const send = useSendBroadcast();
  const { data: drafts } = useDrafts();
  const draft = useSaveDraft();
  const removeDraft = useDeleteDraft();
  const confirm = useConfirm();

  const total = everyone?.recipients ?? 0;
  // No language selected means nobody. The backend reads an empty list as EVERYONE, so the send is
  // blocked here rather than allowed to mean its opposite.
  const recipients = langs.length ? (audience?.recipients ?? 0) : 0;
  const allSelected = langs.length === ALL_LANGS.length;
  const summary = allSelected ? t("bc.langs.all") : joinList(langs.map(langLabel));

  const body = text.trim();
  const overLimit = text.length > MAX_CHARS;
  const filled = buttons.filter((b) => b.text.trim() && b.url.trim());
  const buttonsOk = filled.every((b) => b.url.startsWith("https://"));
  // The broadcast is queued in Redis for the arq worker; if Redis is down it cannot be queued at
  // all, which is worth knowing BEFORE composing rather than after pressing send.
  const queueOk = health?.redis.ok !== false;
  const canSend = Boolean(body) && langs.length > 0 && !overLimit && queueOk && buttonsOk;
  const minutes = Math.max(1, Math.round(recipients / RATE_PER_SEC / 60));

  const byHour = (() => {
    const acc: number[] = new Array(24).fill(0);
    for (const cell of analytics?.heatmap ?? []) acc[cell.hour] += cell.count;
    return acc;
  })();
  const peakHour = byHour.some((n) => n > 0) ? byHour.indexOf(Math.max(...byHour)) : -1;
  // Scheduling defaults to the hour users are most active — the whole reason the strip is here is
  // that scheduling blind is how a broadcast lands at 04:00.
  const sendHour = hour ?? (peakHour >= 0 ? peakHour : 12);

  function saveDraft() {
    if (!body) return;
    draft.mutate(
      {
        id: draftId ?? undefined,
        text: body,
        languages: langs,
        only_active: onlyActive,
        only_referrers: onlyReferrers,
        buttons: filled,
        send_hour: scheduled ? sendHour : null,
      },
      {
        onSuccess: (d) => {
          setDraftId(d.id);
          toast.success(t("bc.draft.saved"));
        },
        onError: () => toast.error(t("bc.draft.failed")),
      },
    );
  }

  function restore(d: BroadcastDraft) {
    setText(d.body);
    setLangs(d.languages ? (d.languages.split(",") as Lang[]) : ALL_LANGS);
    setOnlyActive(d.only_active);
    setOnlyReferrers(d.only_referrers);
    setButtons(d.buttons);
    setScheduled(d.send_hour !== null);
    setHour(d.send_hour);
    setDraftId(d.id);
  }

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
    const at = scheduled ? nextOccurrence(sendHour) : undefined;
    send.mutate(
      {
        text: body,
        languages: langs,
        only_active: onlyActive,
        only_referrers: onlyReferrers,
        buttons: filled,
        scheduled_for: at?.toISOString(),
      },
      {
        onSuccess: (r) => {
          toast.success(
            at
              ? t("bc.schedule.queued", {
                  h: localizeDigits(`${String(sendHour).padStart(2, "0")}:00`),
                })
              : t("bc.send.queued", { n: formatNumber(r.recipients), who: summary }),
          );
          setText("");
          setButtons([]);
          // Sending is what a draft was for; leaving the row behind would offer to restore a
          // message that has already gone out.
          if (draftId !== null) removeDraft.mutate(draftId);
          setDraftId(null);
        },
        onError: () => toast.error(t("bc.send.failed")),
      },
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader title={t("bc.title")} sub={t("bc.sub")} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <Card className="space-y-2">
            <h3 className="text-sm font-bold text-content">{t("bc.audience")}</h3>
            <div className="flex flex-wrap items-center gap-2">
              {ALL_LANGS.map((code) => (
                <Chip key={code} on={langs.includes(code)} onClick={() => toggle(code)}>
                  {langLabel(code)}
                </Chip>
              ))}
              <span className="mx-1 h-5 w-px bg-line" aria-hidden />
              {/* Two refinements the server enforces with the SAME query that produced the count
                  above, so the number here cannot disagree with who the worker walks. */}
              <Chip on={onlyActive} onClick={() => setOnlyActive((v) => !v)}>
                {t("bc.only.active")}
              </Chip>
              <Chip on={onlyReferrers} onClick={() => setOnlyReferrers((v) => !v)}>
                {t("bc.only.referrers")}
              </Chip>
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

          <Card className="space-y-2.5">
            <h3 className="text-sm font-bold text-content">{t("bc.compose")}</h3>
            <MessageField value={text} onChange={setText} placeholder={t("bc.text.placeholder")} />
            <p className="text-xs text-content-subtle">{t("bc.text.hint")}</p>

            <KeyboardBuilder buttons={buttons} onChange={setButtons} />

            <Switch
              checked={scheduled}
              onChange={setScheduled}
              label={t("bc.schedule")}
              hint={t("bc.schedule.hint")}
            />

            {/* Shown whether or not scheduling is on, as the design has it. Hidden behind the
                toggle, the one fact that would make anyone reach for the toggle — that this
                audience is awake at 21:00 — was only visible after you had already decided. It is
                only a CONTROL while scheduling is on; otherwise it is a read-only timing chart. */}
            <div className="space-y-1.5">
              <HourStrip
                counts={byHour}
                mark={scheduled ? sendHour : peakHour}
                onPick={scheduled ? setHour : undefined}
              />
              <p className="text-xs text-content-subtle">
                {peakHour < 0
                  ? t("bc.timing.noData")
                  : scheduled
                    ? t("bc.timing.at", {
                        send: localizeDigits(`${String(sendHour).padStart(2, "0")}:00`),
                        h: localizeDigits(`${String(peakHour).padStart(2, "0")}:00`),
                      })
                    : t("bc.timing.hint", {
                        h: localizeDigits(`${String(peakHour).padStart(2, "0")}:00`),
                      })}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Button onClick={submit} loading={send.isPending} disabled={!canSend}>
                <Send className="h-4 w-4" />
                {t("bc.send")}
              </Button>
              {/* Saving needs a body and nothing else — a draft is by definition unfinished, so
                  gating it on the send's conditions would refuse to keep exactly the half-written
                  message worth keeping. */}
              <Button
                variant="secondary"
                onClick={saveDraft}
                loading={draft.isPending}
                disabled={!body}
              >
                <Save className="h-4 w-4" />
                {t("bc.draft.save")}
              </Button>
              <span className="flex-1" />
              <span className="inline-flex items-center gap-1.5 text-xs text-content-muted">
                <Clock className="h-3.5 w-3.5 text-content-subtle" />
                {t("bc.eta", { m: formatNumber(minutes), rate: formatNumber(RATE_PER_SEC) })}
              </span>
            </div>
          </Card>

          <DraftList
            drafts={drafts ?? []}
            activeId={draftId}
            onRestore={restore}
            onDelete={(id) => {
              removeDraft.mutate(id);
              if (id === draftId) setDraftId(null);
            }}
          />

          <BroadcastHistory />
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          <Card className="space-y-3">
            <h3 className="text-sm font-bold text-content">{t("bc.preview")}</h3>
            {/* A chat frame rather than a lone bubble: half of what lands in Telegram is the header,
                the buttons and the timestamp around it. */}
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
              <div className="space-y-1.5 p-2.5">
                {body ? (
                  <>
                    <div
                      // Sanitised: the panel origin holds the JWTs, so pasted markup must never
                      // execute here even though an admin typed it.
                      className="whitespace-pre-wrap rounded-xl bg-surface-hover px-3 py-2 text-[13px] leading-7"
                      dir="auto"
                      dangerouslySetInnerHTML={{ __html: telegramPreviewHtml(text) }}
                    />
                    {filled.map((b, i) => (
                      <span
                        key={i}
                        className="block truncate rounded-lg bg-brand/20 px-2 py-1.5 text-center text-xs font-semibold text-brand-700"
                      >
                        {b.text}
                      </span>
                    ))}
                    {/* The clock is what the message will carry, not what it carries now — a
                        scheduled send lands at the hour that was chosen. */}
                    <div className="pe-1 text-end text-[10px] text-content-subtle">
                      {localizeDigits(
                        scheduled
                          ? `${String(sendHour).padStart(2, "0")}:00`
                          : new Date().toTimeString().slice(0, 5),
                      )}
                    </div>
                  </>
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
            <PreflightRow ok={buttonsOk}>
              {buttonsOk ? t("bc.pf.buttons") : t("bc.pf.buttonsBad")}
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
