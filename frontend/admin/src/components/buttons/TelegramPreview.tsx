import type { ButtonConfig, Lang } from "@/types/api";

/** Render the screen's visible buttons row-by-row, like a Telegram inline keyboard. */
export function TelegramPreview({ buttons, lang }: { buttons: ButtonConfig[]; lang: Lang }) {
  const visible = buttons.filter((b) => b.is_visible);
  const byRow = new Map<number, ButtonConfig[]>();
  for (const b of visible) {
    const arr = byRow.get(b.effective_row) ?? [];
    arr.push(b);
    byRow.set(b.effective_row, arr);
  }
  const rows = [...byRow.entries()]
    .sort(([a], [b]) => a - b)
    .map(([, btns]) => btns.sort((a, b) => a.effective_position - b.effective_position));

  if (visible.length === 0) {
    return (
      <div className="rounded-xl bg-slate-100 py-6 text-center text-sm text-slate-400 dark:bg-slate-800">
        دکمه‌ای برای نمایش نیست
      </div>
    );
  }

  return (
    <div className="space-y-1.5 rounded-xl border border-slate-200 bg-gradient-to-br from-sky-50 to-indigo-50 p-3 dark:border-slate-700 dark:from-slate-800 dark:to-slate-800">
      {rows.map((row, i) => (
        <div key={i} className="flex gap-1.5">
          {row.map((b) => (
            <div
              key={b.key}
              className="flex-1 truncate rounded-lg bg-white px-3 py-1.5 text-center text-sm shadow-sm dark:bg-slate-700"
            >
              {b.effective_label[lang]}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
