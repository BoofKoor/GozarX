import type { ReactNode } from "react";

/** A titled section divider used to group a long dashboard into scannable bands. */
export function Section({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex items-center gap-3 pt-2">
      <h2 className="shrink-0 text-sm font-semibold text-slate-500 dark:text-slate-400">{title}</h2>
      <div className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
      {action}
    </div>
  );
}
