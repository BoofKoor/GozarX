import { clsx } from "clsx";
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useUpdateButton } from "@/hooks/useButtons";
import type { ButtonConfig, ButtonStyle, Lang } from "@/types/api";

const LANGS: { code: Lang; label: string; dir: "rtl" | "ltr" }[] = [
  { code: "fa", label: "فارسی", dir: "rtl" },
  { code: "en", label: "English", dir: "ltr" },
  { code: "ru", label: "Русский", dir: "ltr" },
];

const COLORS: { value: ButtonStyle; label: string; swatch: string }[] = [
  { value: null, label: "پیش‌فرض", swatch: "bg-line-strong" },
  { value: "primary", label: "آبی", swatch: "bg-brand" },
  { value: "success", label: "سبز", swatch: "bg-success-500" },
  { value: "danger", label: "قرمز", swatch: "bg-danger-500" },
];

/** Modal to edit a button's per-language label, visibility, and color (order is via drag-drop). */
export function ButtonEditor({ button, onClose }: { button: ButtonConfig; onClose: () => void }) {
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
          toast.success("ذخیره شد.");
          onClose();
        },
        onError: () => toast.error("ذخیره نشد."),
      },
    );
  }

  return (
    <Modal onClose={onClose} className="max-w-lg p-5" labelledBy="button-editor-title">
      <div className="mb-1 flex items-center justify-between gap-2">
        <h2 id="button-editor-title" className="text-lg font-bold">
          ویرایش دکمه
        </h2>
        <code
          className="rounded bg-surface-sunken px-1.5 py-0.5 text-xs text-content-muted"
          dir="ltr"
        >
          {button.key}
        </code>
      </div>
      <div className="space-y-3">
        {LANGS.map(({ code, label, dir }) => (
          <div key={code}>
            <label className="mb-1 block text-sm">{label}</label>
            <input
              className="field-control"
              dir={dir}
              value={labels[code]}
              placeholder={button.default_label[code]}
              onChange={(e) => setLabels((s) => ({ ...s, [code]: e.target.value }))}
            />
          </div>
        ))}
        <div>
          <label className="mb-1 block text-sm">نمایش</label>
          <button
            type="button"
            disabled={button.is_critical}
            onClick={() => setVisible((v) => !v)}
            className={clsx(
              "inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition",
              visible
                ? "bg-success-500/12 text-success-700"
                : "bg-surface-sunken text-content-muted",
              button.is_critical && "cursor-not-allowed opacity-60",
            )}
          >
            {visible ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
            {visible ? "نمایش داده می‌شود" : "پنهان"}
          </button>
          {button.is_critical && (
            <p className="mt-2 rounded bg-warning-500/12 p-2 text-xs text-warning-700">
              ⚠️ دکمهٔ حیاتی (بازگشت/تأیید/ناوبری) — قابل مخفی‌سازی نیست تا کاربر در صفحه گیر نیفتد.
            </p>
          )}
        </div>
        <div>
          <label className="mb-1 block text-sm">رنگ دکمه</label>
          <div className="flex gap-2">
            {COLORS.map((c) => (
              <button
                key={c.label}
                type="button"
                onClick={() => setStyle(c.value)}
                className={clsx(
                  "flex flex-col items-center gap-1 rounded-lg border-2 px-3 py-1.5 text-xs transition",
                  style === c.value
                    ? "border-brand"
                    : "border-transparent hover:border-line-strong",
                )}
              >
                <span className={clsx("h-5 w-8 rounded", c.swatch)} />
                {c.label}
              </button>
            ))}
          </div>
          <p className="mt-1 text-xs text-content-subtle">
            رنگ دکمه‌های اینلاین (در نسخه‌های جدید تلگرام نمایش داده می‌شود).
          </p>
        </div>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          انصراف
        </Button>
        <Button onClick={save} loading={update.isPending}>
          ذخیره
        </Button>
      </div>
    </Modal>
  );
}
