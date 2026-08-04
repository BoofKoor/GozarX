import { clsx } from "clsx";
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { useI18n, type MessageKey } from "@/i18n";
import { langLabel } from "@/lib/format";
import { useUpdateButton } from "@/hooks/useButtons";
import type { ButtonConfig, ButtonStyle, Lang } from "@/types/api";

const LANGS: { code: Lang; dir: "rtl" | "ltr" }[] = [
  { code: "fa", dir: "rtl" },
  { code: "en", dir: "ltr" },
  { code: "ru", dir: "ltr" },
];

const COLORS: { value: ButtonStyle; key: MessageKey; swatch: string }[] = [
  { value: null, key: "btn.color.default", swatch: "bg-line-strong" },
  { value: "primary", key: "btn.color.primary", swatch: "bg-brand" },
  { value: "success", key: "btn.color.success", swatch: "bg-success-500" },
  { value: "danger", key: "btn.color.danger", swatch: "bg-danger-500" },
];

/** Modal to edit a button's per-language label, visibility, and color (order is via drag-drop). */
export function ButtonEditor({ button, onClose }: { button: ButtonConfig; onClose: () => void }) {
  const { t } = useI18n();
  const update = useUpdateButton();
  const [labels, setLabels] = useState<Record<Lang, string>>({ ...button.effective_label });
  const [visible, setVisible] = useState(button.is_visible);
  const [style, setStyle] = useState<ButtonStyle>(button.style);

  function save() {
    // Only persist a label that differs from the default; empty -> revert to the code default.
    const override: Partial<Record<Lang, string>> = {};
    (Object.keys(labels) as Lang[]).forEach((code) => {
      const v = labels[code].trim();
      if (v && v !== button.default_label[code]) override[code] = v;
    });
    update.mutate(
      {
        key: button.key,
        patch: {
          labels: Object.keys(override).length ? override : null,
          is_visible: visible,
          style,
        },
      },
      {
        onSuccess: () => {
          toast.success(t("btn.saved"));
          onClose();
        },
        onError: () => toast.error(t("btn.saveFailed")),
      },
    );
  }

  return (
    <Modal onClose={onClose} className="max-w-lg p-5" labelledBy="button-editor-title">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 id="button-editor-title" className="text-lg font-bold">
          {t("btn.editor.title")}
        </h2>
        <code
          className="rounded bg-surface-sunken px-1.5 py-0.5 font-mono text-xs text-content-muted"
          dir="ltr"
        >
          {button.key}
        </code>
      </div>
      <div className="space-y-3">
        {LANGS.map(({ code, dir }, i) => (
          <Field
            key={code}
            label={langLabel(code)}
            hint={i === LANGS.length - 1 ? t("btn.editor.labelHint") : undefined}
          >
            <Input
              dir={dir}
              value={labels[code]}
              placeholder={button.default_label[code]}
              onChange={(e) => setLabels((s) => ({ ...s, [code]: e.target.value }))}
            />
          </Field>
        ))}

        <Field label={t("btn.editor.visibility")}>
          <button
            type="button"
            disabled={button.is_critical}
            onClick={() => setVisible((v) => !v)}
            className={clsx(
              "inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition",
              visible
                ? "bg-success-500/15 text-success-700"
                : "bg-surface-sunken text-content-muted",
              button.is_critical && "cursor-not-allowed opacity-60",
            )}
          >
            {visible ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
            {visible ? t("btn.editor.shown") : t("btn.editor.hidden")}
          </button>
          {button.is_critical && (
            <p className="mt-2 rounded-lg bg-warning-500/15 p-2 text-xs text-warning-700">
              {t("btn.editor.criticalNote")}
            </p>
          )}
        </Field>

        <Field label={t("btn.editor.color")} hint={t("btn.editor.colorHint")}>
          <div className="flex gap-2">
            {COLORS.map((c) => (
              <button
                key={c.key}
                type="button"
                onClick={() => setStyle(c.value)}
                aria-pressed={style === c.value}
                className={clsx(
                  "flex flex-col items-center gap-1 rounded-lg border-2 px-3 py-1.5 text-xs transition",
                  style === c.value
                    ? "border-brand text-content"
                    : "border-transparent text-content-muted hover:border-line-strong",
                )}
              >
                <span className={clsx("h-5 w-8 rounded", c.swatch)} />
                {t(c.key)}
              </button>
            ))}
          </div>
        </Field>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          {t("btn.cancel")}
        </Button>
        <Button onClick={save} loading={update.isPending}>
          {t("btn.save")}
        </Button>
      </div>
    </Modal>
  );
}
