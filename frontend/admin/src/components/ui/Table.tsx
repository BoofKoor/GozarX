import { clsx } from "clsx";
import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from "react";

/**
 * Table primitives. The wrapper owns the horizontal scroll so a wide table never forces the whole
 * page to scroll sideways (which it did on mobile), and the header stays put while long lists
 * scroll inside their own container.
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
    <div className={clsx("scrollbar-thin -mx-5 overflow-x-auto px-5", className)}>
      <table className={clsx("w-full border-collapse text-sm", minWidth)}>{children}</table>
    </div>
  );
}

export function THead({ children }: { children: ReactNode }) {
  return <thead className="sticky top-0 z-10 bg-surface">{children}</thead>;
}

export function TBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-line">{children}</tbody>;
}

export function TR({
  children,
  className,
  onClick,
  selected,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  selected?: boolean;
}) {
  return (
    <tr
      onClick={onClick}
      className={clsx(
        onClick && "cursor-pointer",
        selected ? "bg-brand/[0.07]" : onClick && "hover:bg-surface-hover",
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
      className={clsx(
        "border-b border-line px-3 py-2.5 text-start text-xs font-semibold text-content-muted",
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
    <td className={clsx("px-3 py-2.5 align-middle text-content", className)} {...rest}>
      {children}
    </td>
  );
}
