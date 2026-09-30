import { AlertTriangle, RefreshCw } from "lucide-react";
import { Fragment } from "react";

import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/ui/Spinner";
import { useI18n } from "@/i18n";
import { formatNumber, listSeparator } from "@/lib/format";
import { resolveSelection } from "@/lib/locations";

/**
 * Pick the offered locations from the squad's actual remark names.
 *
 * Both website forms used a free-text box while the exact valid list was already fetched and shown
 * only as a grey hint line underneath — so a typo was a save away, and the backend's rejection was
 * the first sign anything was wrong. When the list can't be fetched (panel down) it falls back to
 * the text box rather than blocking the admin during an outage, and says so.
 *
 * A saved name the squad no longer serves is NAMED here and dropped from what the parent saves
 * (`resolveSelection(...).save`): it used to stay invisibly in the selection, so ticking one new
 * location read "29 of 25" and every save came back 400 for a name no checkbox showed.
 */
export function LocationPicker({
  available,
  loading,
  unavailable,
  selected,
  onChange,
  fallbackText,
  onFallbackTextChange,
  onRefresh,
  refreshing,
}: {
  /** The squad's location names, or undefined while loading / unavailable. */
  available: string[] | undefined;
  loading?: boolean;
  /** True when the list could not be fetched at all (panel unreachable). */
  unavailable?: boolean;
  selected: string[];
  onChange: (next: string[]) => void;
  /** Raw comma-separated text used only in the fallback mode. */
  fallbackText: string;
  onFallbackTextChange: (value: string) => void;
  /** Optional "re-derive from the squad" action (settings page only). */
  onRefresh?: () => void;
  refreshing?: boolean;
}) {
  const { t } = useI18n();
  if (loading) {
    return (
      <div className="flex items-center gap-2 py-2 text-sm text-content-muted">
        <Spinner className="h-4 w-4" />
        {t("loc.loading")}
      </div>
    );
  }

  if (unavailable || !available) {
    return (
      <div className="space-y-2">
        <div className="flex items-start gap-2 rounded-xl bg-warning-500/15 p-2.5 text-xs text-warning-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{t("loc.unavailable")}</span>
        </div>
        <Input
          value={fallbackText}
          onChange={(e) => onFallbackTextChange(e.target.value)}
          placeholder={t("loc.placeholder")}
        />
      </div>
    );
  }

  // A squad that answered with NO locations is a fact about the squad, not an outage: a text box
  // here used to accept names that the save then ignored, and none of them could match a host.
  if (available.length === 0) {
    return (
      <div className="flex items-start gap-2 rounded-xl bg-warning-500/15 p-2.5 text-xs text-warning-700">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{t("loc.emptySquad")}</span>
      </div>
    );
  }

  const { save, stale, all } = resolveSelection(selected, available);
  const ticked = new Set(save);

  function toggle(name: string, checked: boolean) {
    // An EMPTY selection means "all of them" on the backend, so the first untick has to start from
    // the full list rather than from nothing — otherwise unticking one location would silently
    // narrow the picker to a single entry.
    const base = all ? available! : save;
    const next = checked ? [...base, name] : base.filter((l) => l !== name);
    // Unticking the last one would save [] — which means ALL. A site offering nothing is not a
    // choice this control can make, so the last location stays.
    if (next.length === 0) return;
    onChange(next.length === available!.length ? [] : next);
  }

  return (
    <div className="space-y-2.5">
      {stale.length > 0 && (
        <div
          role="status"
          className="flex items-start gap-2 rounded-xl bg-warning-500/15 p-2.5 text-xs text-warning-700"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            {t("loc.stale", { n: formatNumber(stale.length) })}{" "}
            {/* One isolate per NAME: a Persian and a Latin host in one run reorder each other. */}
            {stale.map((name, i) => (
              <Fragment key={name}>
                {i > 0 && listSeparator()}
                <bdi dir="auto" className="font-medium">
                  {name}
                </bdi>
              </Fragment>
            ))}
          </span>
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs text-content-muted">
          {all
            ? t("loc.all", { n: formatNumber(available.length) })
            : t("loc.some", {
                n: formatNumber(save.length),
                total: formatNumber(available.length),
              })}
        </span>
        <div className="flex items-center gap-1">
          <Button type="button" variant="ghost" size="xs" onClick={() => onChange([])}>
            {t("loc.selectAll")}
          </Button>
          {onRefresh && (
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={onRefresh}
              loading={refreshing}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              {t("loc.refresh")}
            </Button>
          )}
        </div>
      </div>
      <div className="grid gap-1.5 rounded-xl border border-line bg-surface-sunken p-3 sm:grid-cols-2">
        {available.map((name) => (
          <Checkbox
            key={name}
            checked={all || ticked.has(name)}
            onChange={(checked) => toggle(name, checked)}
            label={<span dir="auto">{name}</span>}
          />
        ))}
      </div>
      {!all && <p className="text-xs text-content-muted">{t("loc.subsetNote")}</p>}
    </div>
  );
}
