import { clsx } from "clsx";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router-dom";

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
  // `bg-btn`, not `bg-brand`: the design's primary action is periwinkle on the dark console and
  // charcoal on the light one, and a component naming the brand ramp cannot express that.
  // `brightness` rather than a second shade, so the hover follows whichever fill the theme picked.
  primary: "bg-btn text-btn-ink shadow-sm hover:brightness-110 active:brightness-95",
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

interface Look {
  variant?: Variant;
  size?: Size;
  iconOnly?: boolean;
  className?: string;
}

/** The button look, for an element that is not a `<button>` (see `LinkButton`). */
export function buttonClass({
  variant = "primary",
  size = "md",
  iconOnly = false,
  className,
}: Look) {
  return clsx(
    "inline-flex shrink-0 items-center justify-center rounded-xl font-medium transition",
    VARIANTS[variant],
    iconOnly ? `${ICON_SIZES[size]} p-0` : SIZES[size],
    className,
  );
}

/**
 * A router link that LOOKS like a button.
 *
 * Written as `<Link><Button/></Link>` it was a button inside a link — invalid HTML, two tab stops for
 * one action, and a screen reader announcing "link, button". One element, one stop.
 */
export function LinkButton({
  variant,
  size,
  iconOnly,
  className,
  children,
  ...rest
}: Look & Omit<LinkProps, "className"> & { children: ReactNode }) {
  return (
    <Link {...rest} className={buttonClass({ variant, size, iconOnly, className })}>
      {children}
    </Link>
  );
}

/** `LinkButton` for an address outside the console (the live site), opened in a new tab. */
export function ExternalLinkButton({
  variant,
  size,
  iconOnly,
  className,
  children,
  ...rest
}: Look & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "className" | "target" | "rel">) {
  return (
    <a
      {...rest}
      target="_blank"
      rel="noopener noreferrer"
      className={buttonClass({ variant, size, iconOnly, className })}
    >
      {children}
    </a>
  );
}

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
      className={buttonClass({
        variant,
        size,
        iconOnly,
        className: clsx("disabled:pointer-events-none disabled:opacity-50", className),
      })}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <Spinner className={size === "lg" ? "h-5 w-5" : "h-4 w-4"} />}
      {children}
    </button>
  );
}
