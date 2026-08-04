import { Rocket } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { BrandTile } from "@/components/layout/Brand";
import { LanguagePill } from "@/components/layout/LanguagePill";
import { LocationPicker } from "@/components/site/LocationPicker";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Field } from "@/components/ui/Field";
import { NumberInput } from "@/components/ui/NumberInput";
import { Select } from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";
import { useCompleteSetup, useSetupStatus, useSquads } from "@/hooks/useSetup";
import { useSiteDerivableLocations } from "@/hooks/useSite";
import { useI18n } from "@/i18n";
import { apiErrorMessage } from "@/lib/api";
import { splitLocations } from "@/lib/format";
import { allValidNumbers } from "@/lib/validate";

interface Econ {
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  trial_hours: number;
}

const DEFAULT_ECON: Econ = {
  daily_limit_mb: 1024,
  referral_reward_mb: 500,
  referral_reward_limit: 10,
  trial_hours: 24,
};

export function Setup() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { data: status } = useSetupStatus();
  const { data: squads, isLoading, isError } = useSquads();
  const complete = useCompleteSetup();
  const [trialSquad, setTrialSquad] = useState("");
  const [econ, setEcon] = useState<Econ>(DEFAULT_ECON);
  const [locations, setLocations] = useState<string[]>([]);
  const [locationsText, setLocationsText] = useState("");
  // Follows the squad chosen right above it, so the options are always the ones that squad serves.
  const derivable = useSiteDerivableLocations(trialSquad);

  // Setup already done? Don't let a bookmark/back-button re-open the wizard — resubmitting would
  // clobber live settings with the DEFAULT_ECON values. Send the admin to the dashboard instead.
  useEffect(() => {
    if (status?.completed) {
      navigate("/", { replace: true });
    }
  }, [status, navigate]);

  useEffect(() => {
    if (squads && squads.length > 0 && !trialSquad) {
      setTrialSquad(squads[0].uuid);
    }
  }, [squads, trialSquad]);

  // A different squad serves different places, so a selection made against the old one is stale.
  useEffect(() => setLocations([]), [trialSquad]);

  const setNum = (key: keyof Econ) => (n: number) => setEcon((s) => ({ ...s, [key]: n }));
  const picker = derivable.data;
  const pickerUnavailable = derivable.isError || (!derivable.isLoading && !picker);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!trialSquad) {
      toast.error(t("setup.pickSquad"));
      return;
    }
    if (
      !allValidNumbers([
        { value: econ.daily_limit_mb, min: 1 },
        { value: econ.referral_reward_mb, min: 0 },
        { value: econ.referral_reward_limit, min: 0 },
        { value: econ.trial_hours, min: 1 },
      ])
    ) {
      toast.error(t("set.invalidNumbers"));
      return;
    }
    complete.mutate(
      {
        trial_squad: trialSquad,
        locations: pickerUnavailable ? splitLocations(locationsText) : locations,
        ...econ,
        ads_enabled: false,
      },
      {
        onSuccess: () => {
          toast.success(t("setup.done"));
          navigate("/", { replace: true });
        },
        onError: (err) => toast.error(apiErrorMessage(err, t("set.saveFailed"))),
      },
    );
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden p-4">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(60rem_40rem_at_50%_-10%,rgb(var(--brand-500)/0.14),transparent_70%)]"
      />
      <div className="relative w-full max-w-lg">
        <div className="mb-4 flex justify-center">
          <LanguagePill />
        </div>
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <BrandTile className="h-14 w-14" />
          <div>
            <h1 className="text-xl font-bold text-content">{t("setup.title")}</h1>
            <p className="mt-1 text-sm text-content-muted">{t("setup.sub")}</p>
          </div>
        </div>

        <Card>
          <form onSubmit={submit} className="space-y-4">
            <Field label={t("setup.squad")} hint={t("setup.squad.hint")}>
              {isLoading ? (
                <div className="flex justify-center py-4">
                  <Spinner className="h-5 w-5 text-brand" />
                </div>
              ) : isError ? (
                <ErrorState compact message={t("setup.squadsUnreachable")} />
              ) : (
                <Select value={trialSquad} onChange={(e) => setTrialSquad(e.target.value)}>
                  {(squads ?? []).map((s) => (
                    <option key={s.uuid} value={s.uuid}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("set.dailyLimit")}>
                <NumberInput
                  min={1}
                  value={econ.daily_limit_mb}
                  onChange={setNum("daily_limit_mb")}
                />
              </Field>
              <Field label={t("set.trialHours")}>
                <NumberInput min={1} value={econ.trial_hours} onChange={setNum("trial_hours")} />
              </Field>
              <Field label={t("set.rewardMb")}>
                <NumberInput
                  min={0}
                  value={econ.referral_reward_mb}
                  onChange={setNum("referral_reward_mb")}
                />
              </Field>
              <Field label={t("set.rewardLimit")}>
                <NumberInput
                  min={0}
                  value={econ.referral_reward_limit}
                  onChange={setNum("referral_reward_limit")}
                />
              </Field>
            </div>

            <Field label={t("set.locations")} hint={t("set.locations.hint")}>
              <LocationPicker
                available={picker}
                loading={derivable.isLoading}
                unavailable={pickerUnavailable}
                selected={locations}
                onChange={setLocations}
                fallbackText={locationsText}
                onFallbackTextChange={setLocationsText}
              />
            </Field>

            <Button
              type="submit"
              size="lg"
              loading={complete.isPending}
              disabled={!trialSquad}
              className="w-full"
            >
              <Rocket className="h-4 w-4" />
              {t("setup.submit")}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
