import { clsx } from "clsx";
import { Eye, FileText, Save, Search, Undo2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { Switch } from "@/components/ui/Switch";
import { Textarea } from "@/components/ui/Textarea";
import { useI18n } from "@/i18n";
import { formatNumber, langLabel } from "@/lib/format";
import { previewText, useTexts, useUpdateText } from "@/hooks/useTexts";
import type { BotText, Lang } from "@/types/api";

const LANGS: { code: Lang; dir: "rtl" | "ltr" }[] = [
  { code: "fa", dir: "rtl" },
  { code: "en", dir: "ltr" },
  { code: "ru", dir: "ltr" },
];

/** Filled from the panel webhook, so they work in the reminder texts and nowhere else. */
const GLOBAL_VARS = ["total_traffic", "used_traffic", "expire"];

/**
 * Which languages this key is still missing.
 *
 * A blank body is not a style choice — the bot falls back and the user sees Persian. Surfacing it
 * in the list is the only way an operator finds the gap without opening all 57 keys.
 */
function missingLangs(t: BotText): Lang[] {
  return LANGS.map((l) => l.code).filter((c) => !t[c].trim());
}

/**
 * Group by the first underscore segment (`admin_*`, `reminder_*`, `site_*`), folding any one-member
 * group into "other". Derived from the keys themselves, so a new key never needs a map updated
 * here to land somewhere sensible.
 */
function groupKeys(texts: BotText[]): { name: string; items: BotText[] }[] {
  const buckets = new Map<string, BotText[]>();
  for (const t of texts) {
    const head = t.key.includes("_") ? t.key.split("_")[0] : "";
    const bucket = buckets.get(head);
    if (bucket) bucket.push(t);
    else buckets.set(head, [t]);
  }
  const groups: { name: string; items: BotText[] }[] = [];
  const rest: BotText[] = [];
  for (const [name, items] of buckets) {
    if (name && items.length > 1) groups.push({ name, items });
    else rest.push(...items);
  }
  groups.sort((a, b) => b.items.length - a.items.length);
  if (rest.length) groups.push({ name: "", items: rest });
  return groups;
}

export function Texts() {
  const { t } = useI18n();
  const { data: texts = [], isLoading, isError, refetch } = useTexts();
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const visible = useMemo(() => {
    const f = filter.trim().toLowerCase();
    if (!f) return texts;
    return texts.filter((x) => x.key.toLowerCase().includes(f) || x.fa.toLowerCase().includes(f));
  }, [texts, filter]);
  const groups = useMemo(() => groupKeys(visible), [visible]);

  const active = texts.find((x) => x.key === activeKey) ?? null;
  const untranslated = texts.filter((x) => missingLangs(x).length > 0).length;

  return (
    <div className="space-y-6">
      <PageHeader title={t("texts.title")} sub={t("texts.sub", { n: formatNumber(texts.length) })}>
        {untranslated > 0 && (
          <Badge tone="warning">{t("texts.untranslated", { n: formatNumber(untranslated) })}</Badge>
        )}
      </PageHeader>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <Input
            aria-label={t("texts.searchAria")}
            icon={<Search className="h-4 w-4" />}
            placeholder={t("texts.search")}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <div className="mt-3">
            {isError && texts.length === 0 ? (
              <ErrorState compact onRetry={() => refetch()} />
            ) : isLoading ? (
              <div className="flex justify-center py-10">
                <Spinner className="h-6 w-6 text-brand" />
              </div>
            ) : visible.length === 0 ? (
              <EmptyState
                icon={Search}
                title={t("texts.empty.title")}
                message={t("texts.empty.message")}
              />
            ) : (
              <div className="scrollbar-thin max-h-[60vh] space-y-3 overflow-y-auto pe-1">
                {groups.map((g) => (
                  <div key={g.name || "_"}>
                    <div className="mb-1 flex items-center gap-2 px-1">
                      <span className="text-[11px] font-semibold uppercase tracking-wide text-content-subtle">
                        {g.name ? (
                          <span dir="ltr" style={{ unicodeBidi: "isolate" }}>
                            {g.name}
                          </span>
                        ) : (
                          t("texts.group.other")
                        )}
                      </span>
                      <span className="h-px flex-1 bg-line" />
                      <span className="text-[11px] tabular-nums text-content-subtle">
                        {formatNumber(g.items.length)}
                      </span>
                    </div>
                    <ul className="space-y-0.5">
                      {g.items.map((x) => (
                        <li key={x.key}>
                          <KeyRow
                            text={x}
                            active={activeKey === x.key}
                            onClick={() => setActiveKey(x.key)}
                          />
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        <div className="lg:col-span-2">
          {active ? (
            <TextEditor key={active.key} text={active} />
          ) : (
            <Card className="flex h-64 items-center justify-center">
              <EmptyState
                icon={FileText}
                title={t("texts.pick.title")}
                message={t("texts.pick.message")}
              />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function KeyRow({
  text,
  active,
  onClick,
}: {
  text: BotText;
  active: boolean;
  onClick: () => void;
}) {
  const { t } = useI18n();
  const missing = missingLangs(text);
  return (
    <button
      onClick={onClick}
      title={missing.length ? t("texts.missing", { langs: missing.map(langLabel).join("، ") }) : ""}
      className={clsx(
        "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-start text-sm transition",
        active
          ? "bg-brand/15 font-medium text-brand-700"
          : "text-content-muted hover:bg-surface-hover hover:text-content",
      )}
    >
      {/* Logical `start` alignment, not `text-right`: the key is a Latin run, but the ROW belongs
          to the surrounding writing direction. */}
      <span className="min-w-0 flex-1 truncate font-mono text-xs" dir="ltr">
        {text.key}
      </span>
      <span className="flex shrink-0 gap-0.5" aria-hidden>
        {LANGS.map(({ code }) => (
          <i
            key={code}
            className={clsx(
              "h-1.5 w-1.5 rounded-full",
              text[code].trim() ? "bg-success-500" : "bg-warning-500",
            )}
          />
        ))}
      </span>
    </button>
  );
}

function TextEditor({ text }: { text: BotText }) {
  const { t } = useI18n();
  const update = useUpdateText();
  const [bodies, setBodies] = useState<Record<Lang, string>>({
    fa: text.fa,
    en: text.en,
    ru: text.ru,
  });
  const [preview, setPreview] = useState("");
  const [linkPreview, setLinkPreview] = useState(text.link_preview);
  const refs = useRef<Record<Lang, HTMLTextAreaElement | null>>({ fa: null, en: null, ru: null });
  const focused = useRef<Lang>("fa");

  // Debounced live preview of the Farsi body, rendered by the same code the bot uses.
  useEffect(() => {
    const id = setTimeout(() => {
      const sample = Object.fromEntries(text.placeholders.map((p) => [p, `‹${p}›`]));
      previewText(bodies.fa, sample)
        .then((r) => setPreview(r.rendered))
        .catch(() => setPreview(""));
    }, 400);
    return () => clearTimeout(id);
  }, [bodies.fa, text.placeholders]);

  const dirty =
    bodies.fa !== text.fa ||
    bodies.en !== text.en ||
    bodies.ru !== text.ru ||
    linkPreview !== text.link_preview;

  function insertPlaceholder(token: string) {
    const lang = focused.current;
    const ta = refs.current[lang];
    const insert = `{${token}}`;
    if (!ta) {
      setBodies((b) => ({ ...b, [lang]: b[lang] + insert }));
      return;
    }
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    setBodies((b) => ({ ...b, [lang]: b[lang].slice(0, start) + insert + b[lang].slice(end) }));
  }

  function reset() {
    setBodies({ fa: text.fa, en: text.en, ru: text.ru });
    setLinkPreview(text.link_preview);
  }

  function save() {
    update.mutate(
      {
        key: text.key,
        patch: { fa: bodies.fa, en: bodies.en, ru: bodies.ru, link_preview: linkPreview },
      },
      {
        onSuccess: () => toast.success(t("texts.saved")),
        onError: () => toast.error(t("texts.saveFailed")),
      },
    );
  }

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <code className="font-mono text-xs text-content-muted" dir="ltr">
          {text.key}
        </code>
        <span className="flex-1" />
        {dirty && <Badge tone="warning">{t("texts.unsaved")}</Badge>}
      </div>

      {text.placeholders.length > 0 && (
        <TokenRow
          label={t("texts.vars")}
          tokens={text.placeholders}
          onPick={insertPlaceholder}
          className="border-line bg-surface-sunken hover:border-brand"
        />
      )}
      <TokenRow
        label={t("texts.globalVars")}
        tokens={GLOBAL_VARS}
        onPick={insertPlaceholder}
        className="border-warning-500/40 bg-warning-500/15 text-warning-700 hover:border-warning-500"
      />

      {LANGS.map(({ code, dir }) => (
        <Field
          key={code}
          label={
            <span className="flex items-center gap-2">
              {langLabel(code)}
              {!bodies[code].trim() && <Badge tone="warning">{t("texts.blank")}</Badge>}
            </span>
          }
        >
          <Textarea
            ref={(el) => {
              refs.current[code] = el;
            }}
            className="min-h-[90px]"
            dir={dir}
            value={bodies[code]}
            onFocus={() => (focused.current = code)}
            onChange={(e) => setBodies((b) => ({ ...b, [code]: e.target.value }))}
          />
        </Field>
      ))}

      <div>
        <div className="mb-1.5 flex items-center gap-1.5 text-xs text-content-muted">
          <Eye className="h-3.5 w-3.5" />
          {t("texts.preview")}
        </div>
        <div
          className="whitespace-pre-wrap rounded-lg border border-dashed border-line-strong bg-surface-sunken p-3 text-sm"
          dir="rtl"
        >
          {preview || "…"}
        </div>
      </div>

      <Switch
        checked={linkPreview}
        onChange={setLinkPreview}
        label={t("texts.linkPreview")}
        hint={t("texts.linkPreview.hint")}
      />

      <div className="flex justify-end gap-2">
        {dirty && (
          <Button variant="ghost" onClick={reset}>
            <Undo2 className="h-4 w-4" />
            {t("texts.discard")}
          </Button>
        )}
        <Button onClick={save} loading={update.isPending} disabled={!dirty}>
          <Save className="h-4 w-4" />
          {t("texts.save")}
        </Button>
      </div>
    </Card>
  );
}

/** A row of click-to-insert placeholder chips. */
function TokenRow({
  label,
  tokens,
  onPick,
  className,
}: {
  label: string;
  tokens: string[];
  onPick: (token: string) => void;
  className: string;
}) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-medium text-content-muted">{label}</div>
      <div className="flex flex-wrap gap-1.5">
        {tokens.map((p) => (
          <button
            key={p}
            type="button"
            dir="ltr"
            onClick={() => onPick(p)}
            className={clsx("rounded border px-1.5 py-0.5 font-mono text-xs transition", className)}
          >
            {`{${p}}`}
          </button>
        ))}
      </div>
    </div>
  );
}
