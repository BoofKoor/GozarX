import { useI18n } from "@/i18n";
import type { ButtonConfig, Lang } from "@/types/api";

/** Render the screen's visible buttons row-by-row, like a Telegram inline keyboard. */
export function TelegramPreview({ buttons, lang }: { buttons: ButtonConfig[]; lang: Lang }) {
  const { t } = useI18n();
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
      <div className="rounded-xl bg-surface-sunken py-6 text-center text-sm text-content-subtle">
        {t("btn.preview.empty")}
      </div>
    );
  }

  return (
    // A faint brand wash over the SUNKEN surface stands in for a Telegram chat background. The
    // frame has to be darker than the buttons or the keyboard vanishes into the card: `bg-surface`
    // chips on a `bg-surface` card were the same colour, separated only by a shadow.
    <div className="space-y-1.5 rounded-xl border border-line bg-surface-sunken bg-gradient-to-br from-brand/[0.07] to-accent-500/[0.07] p-3">
      {rows.map((row, i) => (
        <div key={i} className="flex gap-1.5">
          {row.map((b) => (
            <div
              key={b.key}
              className="flex-1 truncate rounded-lg border border-line bg-surface px-3 py-1.5 text-center text-sm font-medium shadow-card"
            >
              {b.effective_label[lang]}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
