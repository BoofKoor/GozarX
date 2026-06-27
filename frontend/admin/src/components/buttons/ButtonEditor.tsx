import { clsx } from "clsx";
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { useUpdateButton } from "@/hooks/useButtons";
import type { ButtonConfig, Lang } from "@/types/api";

const LANGS: { code: Lang; label: string; dir: "rtl" | "ltr" }[] = [
  { code: "fa", label: "فارسی", dir: "rtl" },
  { code: "en", label: "English", dir: "ltr" },
  { code: "ru", label: "Русский", dir: "ltr" },
];

/** Modal to edit a button's per-language label + visibility (order is via drag-drop, not here). */
export function ButtonEditor({ button, onClose }: { button: ButtonConfig; onClose: () => void }) {
  const update = useUpdateButton();
  const [labels, setLabels] = useState<Record<Lang, string>>({ ...button.effective_label });
  const [visible, setVisible] = useState(button.is_visible);

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
        patch: { labels: Object.keys(override).length ? override : null, is_visible: visible },
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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-2xl bg-white p-5 shadow-xl dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-1 flex items-center justify-between gap-2">
          <h2 className="text-lg font-bold">ویرایش دکمه</h2>
          <code
            className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500 dark:bg-slate-800"
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
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand dark:border-slate-700 dark:bg-slate-900"
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
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                  : "bg-slate-100 text-slate-500 dark:bg-slate-800",
                button.is_critical && "cursor-not-allowed opacity-60",
              )}
            >
              {visible ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
              {visible ? "نمایش داده می‌شود" : "پنهان"}
            </button>
            {button.is_critical && (
              <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
                ⚠️ دکمهٔ حیاتی (بازگشت/تأیید/ناوبری) — قابل مخفی‌سازی نیست تا کاربر در صفحه گیر
                نیفتد.
              </p>
            )}
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
      </div>
    </div>
  );
}
