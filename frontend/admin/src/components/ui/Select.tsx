import { clsx } from "clsx";
import { ChevronDown } from "lucide-react";
import { forwardRef, type SelectHTMLAttributes } from "react";

import { useFieldInvalid, useFieldProps } from "./Field";

/** Native `<select>` styled to match the panel's inputs, with a custom chevron on the end edge. */
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...rest }, ref) {
    const field = useFieldProps();
    const invalid = useFieldInvalid();
    return (
      <div className="relative">
        <select
          ref={ref}
          className={clsx(
            "field-control cursor-pointer appearance-none pe-9",
            invalid && "field-control-invalid",
            className,
          )}
          {...field}
          {...rest}
        >
          {children}
        </select>
        <ChevronDown
          className="pointer-events-none absolute inset-y-0 end-3 my-auto h-4 w-4 text-content-subtle"
          aria-hidden
        />
      </div>
    );
  },
);
