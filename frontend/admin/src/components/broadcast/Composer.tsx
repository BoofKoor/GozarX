import { clsx } from "clsx";
import { Bold, Italic, Link2, Plus, Trash2 } from "lucide-react";
import { useRef, type ReactNode, type RefObject } from "react";

import { Input } from "@/components/ui/Input";
import { useI18n } from "@/i18n";
import { formatNumber } from "@/lib/format";
import type { BroadcastButton } from "@/types/api";

/** Telegram's own message ceiling — not a house style choice. */
export const MAX_CHARS = 4096;
/** The server's cap too, so the composer cannot offer a fourth button the API will reject. */
export const MAX_BUTTONS = 3;

/**
 * Wrap the textarea's selection in a tag, keeping the caret where the writer left it.
 *
 * The bot sends these messages with `parse_mode="HTML"`, so `<b>`/`<i>`/`<a>` are what Telegram
 * actually renders. Typing them by hand is the failure mode this exists to remove: an unclosed tag
 * makes Telegram reject the WHOLE broadcast, and the operator finds out from a worker log.
 */
function wrapSelection(
  ref: RefObject<HTMLTextAreaElement>,
  value: string,
  onChange: (next: string) => void,
  open: string,
  close: string,
) {
  const el = ref.current;
  if (!el) return;
  const start = el.selectionStart ?? value.length;
  const end = el.selectionEnd ?? start;
  const next = value.slice(0, start) + open + value.slice(start, end) + close + value.slice(end);
  onChange(next);
  // After React re-renders with the new value; without this the caret jumps to the end and the
  // writer has to find their place again after every tag.
  requestAnimationFrame(() => {
    el.focus();
    el.setSelectionRange(start + open.length, end + open.length);
  });
}

function FmtButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className="grid h-7 w-7 place-items-center rounded-md text-content-muted transition hover:bg-surface-hover hover:text-content"
    >
      {children}
    </button>
  );
}

/**
 * The message field: a formatting bar sitting ON the textarea and sharing its border, with the
 * character counter at the bar's far end.
 */
export function MessageField({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder: string;
}) {
  const { t } = useI18n();
  const ref = useRef<HTMLTextAreaElement>(null);
  const over = value.length > MAX_CHARS;
  const wrap = (open: string, close: string) => wrapSelection(ref, value, onChange, open, close);

  return (
    <div>
      <div className="flex items-center gap-0.5 rounded-t-xl border border-b-0 border-line bg-surface-sunken px-1.5 py-1">
        <FmtButton label={t("bc.fmt.bold")} onClick={() => wrap("<b>", "</b>")}>
          <Bold className="h-3.5 w-3.5" />
        </FmtButton>
        <FmtButton label={t("bc.fmt.italic")} onClick={() => wrap("<i>", "</i>")}>
          <Italic className="h-3.5 w-3.5" />
        </FmtButton>
        <FmtButton label={t("bc.fmt.link")} onClick={() => wrap('<a href="https://">', "</a>")}>
          <Link2 className="h-3.5 w-3.5" />
        </FmtButton>
        <span className="flex-1" />
        {/* `dir` and not just an isolate: two numbers around a slash swap places under an RTL base
            direction, so «۱۳۸ / ۴٬۰۹۶» rendered as «۴٬۰۹۶ / ۱۳۸» — the message reading as longer
            than the limit. Safe on an inline run; never on a block. */}
        <span
          dir="ltr"
          className={clsx(
            "px-1 text-xs tabular-nums",
            over ? "font-bold text-danger-700" : "text-content-subtle",
          )}
        >
          {formatNumber(value.length)} / {formatNumber(MAX_CHARS)}
        </span>
      </div>
      {/* Four lines at the design's 1.8 leading, not 180px. A broadcast is a paragraph; sizing the
          field for an essay pushed the button builder, the schedule and the send button below the
          fold and made the page 35% taller than the reference for the same content. It still grows
          as you type — the browser scrolls it. */}
      <textarea
        ref={ref}
        className="field-control min-h-[7rem] rounded-t-none leading-[1.8]"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        dir="auto"
      />
    </div>
  );
}

/**
 * The inline keyboard the bot will attach.
 *
 * It lives in the composer rather than behind a settings screen because the bot genuinely sends
 * these, and a call to action is part of the message being written — not configuration. The URL
 * field shows its own error: Telegram rejects a non-`https://` link and fails the whole message, so
 * the operator has to see that here rather than in a worker log after pressing send.
 */
export function KeyboardBuilder({
  buttons,
  onChange,
}: {
  buttons: BroadcastButton[];
  onChange: (next: BroadcastButton[]) => void;
}) {
  const { t } = useI18n();
  const set = (i: number, patch: Partial<BroadcastButton>) =>
    onChange(buttons.map((b, j) => (j === i ? { ...b, ...patch } : b)));

  return (
    <div className="space-y-2">
      <label className="block text-xs font-medium text-content-muted">{t("bc.kb")}</label>
      {buttons.map((b, i) => {
        const bad = b.url.length > 0 && !b.url.startsWith("https://");
        return (
          <div key={i} className="space-y-1">
            <div className="grid grid-cols-[1fr_1.5fr_auto] items-start gap-2">
              <Input
                aria-label={t("bc.kb.text")}
                placeholder={t("bc.kb.text")}
                value={b.text}
                maxLength={64}
                onChange={(e) => set(i, { text: e.target.value })}
              />
              <Input
                aria-label={t("bc.kb.url")}
                placeholder="https://"
                value={b.url}
                dir="ltr"
                onChange={(e) => set(i, { url: e.target.value })}
                className={bad ? "field-control-invalid" : undefined}
              />
              <button
                type="button"
                onClick={() => onChange(buttons.filter((_, j) => j !== i))}
                aria-label={t("bc.kb.remove")}
                className="grid h-9 w-9 place-items-center rounded-lg border border-transparent text-content-subtle transition hover:border-danger-500/40 hover:text-danger-700"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
            {bad && <p className="text-[11px] text-danger-700">{t("bc.kb.urlBad")}</p>}
          </div>
        );
      })}
      {buttons.length < MAX_BUTTONS && (
        <button
          type="button"
          onClick={() => onChange([...buttons, { text: "", url: "" }])}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand hover:underline"
        >
          <Plus className="h-3.5 w-3.5" />
          {t("bc.kb.add")}
        </button>
      )}
    </div>
  );
}
