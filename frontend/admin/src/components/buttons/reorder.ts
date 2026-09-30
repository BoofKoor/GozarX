import type { ReorderItem } from "@/types/api";

export interface RowLayout {
  row: number;
  keys: string[];
}

/**
 * Where a drop puts things: the reorder request for dragging `activeId` onto `overId` — a button
 * key, a row's drop zone (`rowzone-<n>`) or the "new row" zone (`newrow`). `null` for a no-op.
 *
 * Pure so it can be tested; the four things it used to get wrong are each pinned there:
 *
 * - A row holding a LOCKED button (`locked`: back, confirm) keeps its real number, because the
 *   server pins those to their structural row. Renumbered from zero, rows drifted off them — a
 *   button moved below an emptied row took the same number as "back" and merged into its row.
 * - Every other row is numbered densely around them, in order. Kept verbatim, "new row" was max + 1
 *   on every move and nothing ever came back down: the 98th move on a three-button screen asked for
 *   row 100, which the server's cap (99) refused — and every "new row" drop after it. The bot packs
 *   rows densely either way, so the numbers only have to keep the ORDER.
 * - arrayMove's rule, on the order the screen SHOWS: a forward move lands after the button dropped
 *   on, a backward one before it. Always inserting before put every forward move one slot short.
 * - "New row" is one past the last row that still has something once the button has left, so a
 *   lone last-row button dropped there again stays put instead of counting upward.
 */
export function planReorder(
  rows: RowLayout[],
  activeId: string,
  overId: string,
  locked: ReadonlySet<string> = new Set(),
): ReorderItem[] | null {
  const visual = rows.flatMap((r) => r.keys);
  const layout = rows.map((r) => ({ row: r.row, keys: r.keys.filter((k) => k !== activeId) }));

  let targetRow: number;
  let dropAt: string | null = null;
  if (overId.startsWith("rowzone-")) {
    targetRow = Number(overId.slice("rowzone-".length));
  } else if (overId === "newrow") {
    const occupied = layout.filter((r) => r.keys.length > 0).map((r) => r.row);
    targetRow = (occupied.length ? Math.max(...occupied) : -1) + 1;
  } else {
    const owner = rows.find((r) => r.keys.includes(overId));
    if (!owner) return null;
    targetRow = owner.row;
    dropAt = overId;
  }
  if (activeId === dropAt) return null;

  let target = layout.find((r) => r.row === targetRow);
  if (!target) {
    target = { row: targetRow, keys: [] };
    layout.push(target);
  }
  if (dropAt) {
    const forward = visual.indexOf(activeId) < visual.indexOf(dropAt);
    const idx = target.keys.indexOf(dropAt);
    target.keys.splice(idx < 0 ? target.keys.length : forward ? idx + 1 : idx, 0, activeId);
  } else {
    target.keys.push(activeId);
  }

  // A new row is only ever added after the last one, so the rows ahead of a locked row R all had
  // distinct numbers below R: numbered densely, they still fit under it.
  const items: ReorderItem[] = [];
  let next = 0;
  for (const r of layout.filter((l) => l.keys.length > 0).sort((a, b) => a.row - b.row)) {
    const row = r.keys.some((k) => locked.has(k)) ? r.row : next;
    next = row + 1;
    items.push(...r.keys.map((key, position) => ({ key, row_index: row, position })));
  }
  return items;
}
