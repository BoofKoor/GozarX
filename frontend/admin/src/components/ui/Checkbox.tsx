import { clsx } from "clsx";
import { Check } from "lucide-react";
import type { ReactNode } from "react";

/** Labelled checkbox. The native input stays in the DOM (form semantics, a11y) but is visually
 *  replaced by a themed box so it looks right in both light and dark. */
export function Checkbox({
  checked,
  onChange,
  label,
  disabled,
  className,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: ReactNode;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <label
      className={clsx(
        "group inline-flex cursor-pointer items-center gap-2 text-sm text-content",
        disabled && "cursor-not-allowed opacity-60",
        className,
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden
        className={clsx(
          "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition",
          "peer-focus-visible:ring-2 peer-focus-visible:ring-brand/45 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-canvas",
          checked ? "border-brand bg-brand text-white" : "border-line-strong bg-surface",
        )}
      >
        {checked && <Check className="h-3 w-3" strokeWidth={3} />}
      </span>
      <span className="min-w-0">{label}</span>
    </label>
  );
}
