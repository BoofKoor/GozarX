import { clsx } from "clsx";
import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from "react";

/**
 * Table primitives.
 *
 * The wrapper owns the horizontal scroll so a wide table never forces the whole page to scroll
 * sideways (which it did on mobile), and the header stays put while long lists scroll inside their
 * own container.
 *
 * A table is FLUSH with its card: the design gives the header its own tinted band running the full
 * width, which an inset table cannot draw — the band would float with a gutter on each side and
 * stop reading as the table's own top edge. So the card holds no padding and the table's own cell
 * padding is the inset. Put a table in `<Card padded={false} className="overflow-hidden">`.
 */
export function Table({
  children,
  className,
  minWidth = "min-w-[640px]",
}: {
  children: ReactNode;
  className?: string;
  /** Below this width the wrapper scrolls instead of squashing columns. */
  minWidth?: string;
}) {
  return (
    <div className={clsx("scrollbar-thin overflow-x-auto", className)}>
      <table className={clsx("w-full border-collapse text-sm", minWidth)}>{children}</table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  // A band, not a bare row. `bg-surface` is the CARD's colour, so the header was invisible and the
  // first data row read as the header.
  return <thead className="sticky top-0 z-10 bg-surface-raised">{children}</thead>;
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-line">{children}</tbody>;
}

export function TR({
  children,
  className,
  onClick,
  selected,
  label,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  selected?: boolean;
  /** Accessible name for an activatable row — what the record IS, e.g. the handle or id. */
  label?: string;
}) {
  // A row that opens a record has to be operable by keyboard, not only by mouse. Users and
  // SiteDevices both open their detail dialog from a row click, so without this a keyboard-only
  // operator could not open a single record on either page.
  const activatable = Boolean(onClick);
  return (
    <tr
      onClick={onClick}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault(); // Space would otherwise scroll the page
                onClick();
              }
            }
          : undefined
      }
      tabIndex={activatable ? 0 : undefined}
      role={activatable ? "button" : undefined}
      aria-label={activatable ? label : undefined}
      className={clsx(
        activatable && "cursor-pointer focus-visible:relative focus-visible:z-10",
        selected ? "bg-brand/15" : activatable && "hover:bg-surface-hover",
        "transition-colors",
        className,
      )}
    >
      {children}
    </tr>
  );
}

export function TH({
  children,
  className,
  ...rest
}: ThHTMLAttributes<HTMLTableCellElement> & { children?: ReactNode }) {
  return (
    <th
      scope="col"
      className={clsx(
        "px-4 py-2.5 text-start text-xs font-semibold text-content-subtle",
        className,
      )}
      {...rest}
    >
      {children}
    </th>
  );
}

export function TD({
  children,
  className,
  ...rest
}: TdHTMLAttributes<HTMLTableCellElement> & { children?: ReactNode }) {
  return (
    <td className={clsx("px-4 py-2.5 align-middle text-content", className)} {...rest}>
      {children}
    </td>
  );
}
