import { clsx } from "clsx";
import type { ReactNode } from "react";

/**
 * Labelled on/off toggle. Renders a real `role="switch"` button (keyboard operable, announced with
 * its state) — the panel previously used bare `<input type="checkbox">` with the label text sitting
 * next to it as plain markup.
 */
export function Switch({
  checked,
  onChange,
  label,
  hint,
  disabled,
  className,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: ReactNode;
  hint?: ReactNode;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={clsx(
        "flex w-full items-start gap-3 rounded-xl p-1 text-start transition",
        "disabled:pointer-events-none disabled:opacity-60",
        className,
      )}
    >
      <span
        className={clsx(
          "mt-0.5 flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition-colors",
          checked ? "bg-brand" : "bg-line-strong",
        )}
        aria-hidden
      >
        <span
          className={clsx(
            "h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
            // RTL: the "on" position is the LEFT end of the track.
            checked ? "-translate-x-4" : "translate-x-0",
          )}
        />
      </span>
      <span className="min-w-0">
        <span className="block text-sm text-content">{label}</span>
        {hint && <span className="mt-0.5 block text-xs text-content-muted">{hint}</span>}
      </span>
    </button>
  );
}
