import { clsx } from "clsx";
import { forwardRef, type TextareaHTMLAttributes } from "react";

import { useFieldInvalid, useFieldProps } from "./Field";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...rest }, ref) {
  const field = useFieldProps();
  const invalid = useFieldInvalid();
  return (
    <textarea
      ref={ref}
      className={clsx(
        "field-control min-h-[96px] resize-y leading-relaxed",
        invalid && "field-control-invalid",
        className,
      )}
      {...field}
      {...rest}
    />
  );
});
