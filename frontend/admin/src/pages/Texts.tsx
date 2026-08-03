import { Eye, FileText, Save, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { previewText, useTexts, useUpdateText } from "@/hooks/useTexts";
import type { BotText, Lang } from "@/types/api";

const LANGS: { code: Lang; label: string; dir: "rtl" | "ltr" }[] = [
  { code: "fa", label: "فارسی", dir: "rtl" },
  { code: "en", label: "English", dir: "ltr" },
  { code: "ru", label: "Русский", dir: "ltr" },
];

// Dynamic variables filled from the panel webhook — usable in the reminder texts.
const GLOBAL_VARS = ["total_traffic", "used_traffic", "expire"];

export function Texts() {
  const { data: texts = [], isLoading, isError, refetch } = useTexts();
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const visible = useMemo(() => {
    const f = filter.trim().toLowerCase();
    if (!f) return texts;
    return texts.filter((t) => t.key.toLowerCase().includes(f) || t.fa.toLowerCase().includes(f));
  }, [texts, filter]);

  const active = texts.find((t) => t.key === activeKey) ?? null;

  return (
    <div className="space-y-6">
      <PageHeader title="متن‌ها" />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <div className="relative mb-3">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-content-subtle" />
            <input
              aria-label="جستجوی متن‌ها"
              className="field-control ps-9"
              placeholder="جستجو…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          {isError && texts.length === 0 ? (
            <ErrorState compact onRetry={() => refetch()} />
          ) : isLoading ? (
            <div className="flex justify-center py-10">
              <Spinner className="h-6 w-6 text-brand" />
            </div>
          ) : (
            <ul className="max-h-[60vh] space-y-1 overflow-y-auto">
              {visible.map((t) => (
                <li key={t.key}>
                  <button
                    onClick={() => setActiveKey(t.key)}
                    className={`w-full truncate rounded-lg px-2 py-1.5 text-right text-sm transition ${
                      activeKey === t.key
                        ? "bg-brand/10 text-brand"
                        : "text-content-muted hover:bg-surface-hover"
                    }`}
                    dir="ltr"
                  >
                    {t.key}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="lg:col-span-2">
          {active ? (
            <TextEditor key={active.key} text={active} />
          ) : (
            <Card className="flex h-64 items-center justify-center text-content-subtle">
              <div className="text-center">
                <FileText className="mx-auto mb-2 h-8 w-8" />
                یک متن را برای ویرایش انتخاب کنید
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function TextEditor({ text }: { text: BotText }) {
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

  // Debounced live preview of the Farsi body (same render logic the bot uses).
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

  function save() {
    update.mutate(
      {
        key: text.key,
        patch: { fa: bodies.fa, en: bodies.en, ru: bodies.ru, link_preview: linkPreview },
      },
      {
        onSuccess: () => toast.success("ذخیره شد."),
        onError: () => toast.error("ذخیره نشد."),
      },
    );
  }

  return (
    <Card className="space-y-4">
      <code className="text-xs text-content-subtle" dir="ltr">
        {text.key}
      </code>

      {text.placeholders.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-medium text-content-muted">
            متغیرها (برای درج کلیک کنید):
          </div>
          <div className="flex flex-wrap gap-1.5">
            {text.placeholders.map((p) => (
              <button
                key={p}
                type="button"
                dir="ltr"
                onClick={() => insertPlaceholder(p)}
                className="rounded border border-line bg-surface-sunken px-1.5 py-0.5 font-mono text-xs hover:border-brand"
              >
                {`{${p}}`}
              </button>
            ))}
          </div>
        </div>
      )}

      <div>
        <div className="mb-1.5 text-xs font-medium text-content-muted">
          متغیرهای سراسری (در پیام‌های یادآور پر می‌شوند — برای درج کلیک کنید):
        </div>
        <div className="flex flex-wrap gap-1.5">
          {GLOBAL_VARS.map((p) => (
            <button
              key={p}
              type="button"
              dir="ltr"
              onClick={() => insertPlaceholder(p)}
              className="rounded border border-warning-500/40 bg-warning-500/12 px-1.5 py-0.5 font-mono text-xs text-warning-700 hover:border-warning-500"
            >
              {`{${p}}`}
            </button>
          ))}
        </div>
      </div>

      {LANGS.map(({ code, label, dir }) => (
        <div key={code}>
          <label className="mb-1 block text-sm">{label}</label>
          <textarea
            ref={(el) => (refs.current[code] = el)}
            className="field-control min-h-[90px]"
            dir={dir}
            value={bodies[code]}
            onFocus={() => (focused.current = code)}
            onChange={(e) => setBodies((b) => ({ ...b, [code]: e.target.value }))}
          />
        </div>
      ))}

      <div>
        <div className="mb-1.5 flex items-center gap-1.5 text-xs text-content-muted">
          <Eye className="h-3.5 w-3.5" />
          پیش‌نمایش (فارسی):
        </div>
        <div
          className="whitespace-pre-wrap rounded-lg border border-dashed border-line-strong bg-surface-sunken p-3 text-sm"
          dir="rtl"
        >
          {preview || "…"}
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={linkPreview}
          onChange={(e) => setLinkPreview(e.target.checked)}
          className="h-4 w-4 accent-brand"
        />
        نمایش پیش‌نمایش لینک در این پیام
      </label>

      <div className="flex justify-end">
        <Button onClick={save} loading={update.isPending} disabled={!dirty}>
          <Save className="h-4 w-4" />
          ذخیره
        </Button>
      </div>
    </Card>
  );
}
