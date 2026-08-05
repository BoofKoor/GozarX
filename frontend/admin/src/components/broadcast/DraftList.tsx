import { clsx } from "clsx";
import { FileText, Trash2 } from "lucide-react";

import { Card } from "@/components/ui/Card";
import { useI18n } from "@/i18n";
import { faRelative, joinList, langLabel } from "@/lib/format";
import type { BroadcastDraft } from "@/types/api";

/**
 * Saved-but-unsent broadcasts.
 *
 * Hidden entirely when there are none: an empty shelf beside a composer is a permanent reminder of
 * a feature rather than a place anything is kept. `EmptyState` is for a list someone navigated TO.
 *
 * Restoring replaces what is in the composer, so the row says which draft is currently loaded —
 * without that marker, pressing save after a restore looks like it might mint a second copy.
 */
export function DraftList({
  drafts,
  activeId,
  onRestore,
  onDelete,
}: {
  drafts: BroadcastDraft[];
  activeId: number | null;
  onRestore: (draft: BroadcastDraft) => void;
  onDelete: (id: number) => void;
}) {
  const { t } = useI18n();
  if (!drafts.length) return null;

  return (
    <Card padded={false} className="overflow-hidden">
      <h3 className="px-card pb-2 pt-card text-sm font-bold text-content">{t("bc.draft.title")}</h3>
      <ul>
        {drafts.map((d) => {
          // `joinList` owns the separator, which differs by locale — «، » is not a comma.
          const langs = d.languages ? joinList(d.languages.split(",").map(langLabel)) : null;
          return (
            <li
              key={d.id}
              className={clsx(
                "flex items-center gap-2.5 border-t border-line px-card py-2.5 transition",
                d.id === activeId ? "bg-brand/10" : "hover:bg-surface-hover",
              )}
            >
              <button
                type="button"
                onClick={() => onRestore(d)}
                className="flex min-w-0 flex-1 items-center gap-2.5 text-start"
              >
                <FileText className="h-4 w-4 shrink-0 text-content-subtle" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[0.8rem] text-content">
                    {d.title || t("bc.draft.untitled")}
                  </span>
                  <span className="block truncate text-[11px] text-content-subtle">
                    {faRelative(d.updated_at)}
                    {langs ? ` · ${langs}` : ""}
                  </span>
                </span>
              </button>
              <button
                type="button"
                onClick={() => onDelete(d.id)}
                aria-label={t("bc.draft.delete")}
                className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-content-subtle transition hover:bg-danger-500/15 hover:text-danger-700"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
