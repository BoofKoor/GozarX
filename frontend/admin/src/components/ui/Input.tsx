import { clsx } from "clsx";
import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

import { useFieldInvalid, useFieldProps } from "./Field";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  /** Leading adornment (icon) — placed on the start edge, RTL-aware. */
  icon?: ReactNode;
  /** Trailing adornment (unit label, action button). */
  suffix?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { className, icon, suffix, ...rest },
  ref,
) {
  const field = useFieldProps();
  const invalid = useFieldInvalid();
  const control = (
    <input
      ref={ref}
      className={clsx(
        "field-control",
        invalid && "field-control-invalid",
        icon && "ps-9",
        suffix && "pe-12",
        className,
      )}
      {...field}
      {...rest}
    />
  );

  if (!icon && !suffix) return control;
  return (
    <div className="relative">
      {icon && (
        <span
          className="pointer-events-none absolute inset-y-0 start-0 flex w-9 items-center justify-center text-content-subtle"
          aria-hidden
        >
          {icon}
        </span>
      )}
      {control}
      {suffix && (
        <span className="absolute inset-y-0 end-0 flex items-center pe-3 text-xs text-content-subtle">
          {suffix}
        </span>
      )}
    </div>
  );
});
