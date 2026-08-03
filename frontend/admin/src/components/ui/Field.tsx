import { clsx } from "clsx";
import { createContext, type ReactNode, useContext, useId } from "react";

/**
 * Label + hint + error wrapper for a single form control.
 *
 * Replaces the four hand-copied `Labeled`/`Field` helpers that lived inside Settings, SiteSettings,
 * SiteSetup, SitePush and SiteLandingPages — none of which associated the label with its input, so
 * clicking a label did nothing and screen readers announced the control unlabelled.
 *
 * The generated id + `aria-describedby` + `aria-invalid` are published through context; the controls
 * in this folder (`Input`, `Textarea`, `Select`, `NumberInput`) pick them up automatically.
 */
interface FieldContext {
  id: string;
  describedBy?: string;
  invalid: boolean;
}

const Ctx = createContext<FieldContext | null>(null);

/** Controls call this to inherit their Field's id/aria wiring. Safe to use outside a Field. */
export function useFieldProps(): {
  id?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
} {
  const ctx = useContext(Ctx);
  if (!ctx) return {};
  return {
    id: ctx.id,
    "aria-describedby": ctx.describedBy,
    "aria-invalid": ctx.invalid || undefined,
  };
}

/** True when the enclosing Field is in an error state — controls use it to tint their border. */
export function useFieldInvalid(): boolean {
  return useContext(Ctx)?.invalid ?? false;
}

export function Field({
  label,
  hint,
  error,
  required,
  className,
  children,
}: {
  label?: ReactNode;
  /** Explanatory copy under the control. Hidden while an `error` is showing. */
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const base = useId();
  const id = `${base}-control`;
  const hintId = `${base}-hint`;
  const errorId = `${base}-error`;
  const invalid = Boolean(error);
  const describedBy = invalid ? errorId : hint ? hintId : undefined;

  return (
    <Ctx.Provider value={{ id, describedBy, invalid }}>
      <div className={clsx("space-y-1.5", className)}>
        {label && (
          <label htmlFor={id} className="block text-sm font-medium text-content">
            {label}
            {required && (
              <span className="mr-1 text-danger-500" aria-hidden>
                *
              </span>
            )}
          </label>
        )}
        {children}
        {invalid ? (
          <p id={errorId} role="alert" className="text-xs text-danger-600">
            {error}
          </p>
        ) : (
          hint && (
            <p id={hintId} className="text-xs text-content-muted">
              {hint}
            </p>
          )
        )}
      </div>
    </Ctx.Provider>
  );
}
