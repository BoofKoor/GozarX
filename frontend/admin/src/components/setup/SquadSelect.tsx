import { Info } from "lucide-react";

import { ErrorState } from "@/components/ui/ErrorState";
import { Select } from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";
import { useSquads } from "@/hooks/useSetup";
import { useI18n } from "@/i18n";

/**
 * The squad picker both setup wizards open with — one component, so the two cannot drift apart.
 *
 * It covers the two states the wizards used to leave the operator stuck in. A failed list had no
 * way to ask again: the error box was all there was, and only a reload got past it. An EMPTY list
 * drew an empty menu above a disabled submit button, with nothing to say that the panel simply has
 * no internal squads yet — which is the one thing the operator needed to hear to fix it.
 */
export function SquadSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (uuid: string) => void;
}) {
  const { t } = useI18n();
  const squads = useSquads();
  if (squads.isLoading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner className="h-5 w-5 text-brand" />
      </div>
    );
  }
  if (squads.isError) {
    return (
      <ErrorState
        compact
        message={t("setup.squadsUnreachable")}
        onRetry={() => void squads.refetch()}
      />
    );
  }
  if ((squads.data ?? []).length === 0) {
    return (
      <p
        role="status"
        className="flex items-start gap-2 rounded-xl bg-warning-500/15 p-3 text-xs text-warning-700"
      >
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="min-w-0 flex-1">{t("setup.squadsEmpty")}</span>
        <button
          type="button"
          className="shrink-0 font-semibold underline"
          onClick={() => void squads.refetch()}
        >
          {t("ui.retry")}
        </button>
      </p>
    );
  }
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)}>
      {(squads.data ?? []).map((s) => (
        <option key={s.uuid} value={s.uuid}>
          {s.name}
        </option>
      ))}
    </Select>
  );
}
