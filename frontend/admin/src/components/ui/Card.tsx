import { clsx } from "clsx";
import type { ComponentType, ReactNode } from "react";

interface CardProps {
  className?: string;
  children: ReactNode;
  /** Drop the default inner padding (for cards that own their own layout, e.g. a table). */
  padded?: boolean;
  /** Lift + accent border on hover — for clickable/linked cards. */
  interactive?: boolean;
}

export function Card({ className, children, padded = true, interactive = false }: CardProps) {
  return (
    <div
      className={clsx(
        // No border. A card is separated from the well by its own SURFACE, which is what the design
        // does everywhere — nothing in the reference carries an outline, and the dashboard's tiles
        // (which never used this component) had none either, so the panel was drawing two different
        // kinds of card. The 1px `--line` ring around every panel is most of why the console read
        // boxier and flatter than the design it was built from.
        "rounded-card bg-surface shadow-card",
        padded && "p-card",
        interactive &&
          "cursor-pointer transition hover:-translate-y-0.5 hover:shadow-raised hover:ring-1 hover:ring-brand/40",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Header row for a card: a title (+ optional icon and sub-line) on one side, actions on the other. */
export function CardHeader({
  title,
  sub,
  icon: Icon,
  action,
  className,
}: {
  title: ReactNode;
  sub?: ReactNode;
  icon?: ComponentType<{ className?: string }>;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("mb-4 flex items-start justify-between gap-3", className)}>
      <div className="flex min-w-0 items-start gap-2">
        {Icon && <Icon className="mt-0.5 h-4 w-4 shrink-0 text-content-subtle" />}
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-content">{title}</div>
          {sub && <div className="mt-0.5 text-xs text-content-muted">{sub}</div>}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/** Footer strip for a card — separated by a hairline, used for form actions. */
export function CardFooter({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={clsx(
        "-mx-card -mb-card mt-card flex items-center justify-end gap-2 border-t border-line px-card py-3",
        className,
      )}
    >
      {children}
    </div>
  );
}
