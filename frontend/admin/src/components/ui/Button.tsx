import { clsx } from "clsx";
import type { ButtonHTMLAttributes } from "react";

import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "ghost" | "outline" | "danger";
type Size = "xs" | "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  loading?: boolean;
  variant?: Variant;
  size?: Size;
  /** Square icon-only button — pass an `aria-label` so it stays announced. */
  iconOnly?: boolean;
}

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-white shadow-sm hover:bg-brand-600 active:bg-brand-700",
  secondary: "bg-surface-sunken text-content hover:bg-surface-hover",
  ghost: "text-content-muted hover:bg-surface-hover hover:text-content",
  outline: "border border-line-strong bg-surface text-content hover:bg-surface-hover",
  danger: "bg-danger text-white shadow-sm hover:bg-danger-700 active:bg-danger-700",
};

const SIZES: Record<Size, string> = {
  xs: "h-7 gap-1 px-2 text-xs",
  sm: "h-8 gap-1.5 px-3 text-xs",
  md: "h-9 gap-2 px-4 text-sm",
  lg: "h-11 gap-2 px-5 text-base",
};

const ICON_SIZES: Record<Size, string> = {
  xs: "h-7 w-7",
  sm: "h-8 w-8",
  md: "h-9 w-9",
  lg: "h-11 w-11",
};

export function Button({
  loading,
  variant = "primary",
  size = "md",
  iconOnly = false,
  className,
  children,
  disabled,
  type = "button",
  ...rest
}: Props) {
  return (
    <button
      type={type}
      className={clsx(
        "inline-flex shrink-0 items-center justify-center rounded-xl font-medium transition",
        "disabled:pointer-events-none disabled:opacity-50",
        VARIANTS[variant],
        iconOnly ? `${ICON_SIZES[size]} p-0` : SIZES[size],
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <Spinner className={size === "lg" ? "h-5 w-5" : "h-4 w-4"} />}
      {children}
    </button>
  );
}
