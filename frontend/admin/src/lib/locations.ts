/**
 * Location names as the server compares them.
 *
 * `normalizeRemark` mirrors the backend's `gozar.remnawave.links.normalize_remark` — template tokens
 * dropped, NFKC, the invisible joiners removed, spacing and case folded — because that is the key
 * the server validates a saved list with. Comparing verbatim here while the server compared
 * normalised is how a name could read as "not offered" in one place and "served" in the other.
 * It is only ever a join key; the squad's own spelling is what gets shown and saved.
 */
const TEMPLATE = /\{\{.*?\}\}/g;

export function normalizeRemark(name: string): string {
  return name
    .replace(TEMPLATE, " ")
    .normalize("NFKC")
    .replace(/‌/g, " ")
    .replace(/[‍﻿]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

export interface LocationSelection {
  /** What a save sends: the ticked names in the squad's spelling, or `[]` for "all of them". */
  save: string[];
  /** Saved names the squad no longer serves — shown, then dropped on the next save. */
  stale: string[];
  /** Every location is offered (an empty list, or every one of them ticked). */
  all: boolean;
}

/**
 * Reconcile a saved selection with what the squad offers now.
 *
 * A saved name the squad stopped serving (a host renamed or hidden in the panel) used to stay in
 * the form invisibly — no checkbox showed it — and rode along on every save, which the server then
 * refused with a 400 naming it. Ticking one new location read "29 of 25 selected" and could not be
 * saved at all. Stale names are reported instead, and never sent.
 *
 * Everything ticked collapses to `[]`, which the server reads as "all of them, live": a host added
 * in the panel later then appears by itself rather than waiting for someone to tick it.
 */
export function resolveSelection(selected: string[], available: string[]): LocationSelection {
  const byKey = new Map(available.map((name) => [normalizeRemark(name), name]));
  const kept: string[] = [];
  const stale: string[] = [];
  for (const name of selected) {
    const live = byKey.get(normalizeRemark(name));
    if (live === undefined) stale.push(name);
    else if (!kept.includes(live)) kept.push(live);
  }
  const all = kept.length === 0 || kept.length === available.length;
  return { save: all ? [] : kept, stale, all };
}
