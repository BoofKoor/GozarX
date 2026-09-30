import { AlertTriangle, Coins, Gift, MapPin, Server } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { LocationPicker } from "@/components/site/LocationPicker";
import { SiteTabs } from "@/components/site/SiteTabs";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Field } from "@/components/ui/Field";
import { NumberInput } from "@/components/ui/NumberInput";
import { PageHeader } from "@/components/ui/PageHeader";
import { Select } from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";
import { useSquads } from "@/hooks/useSetup";
import { useCompleteSiteSetup, useSiteDerivableLocations, useSiteSettings } from "@/hooks/useSite";
import { useI18n } from "@/i18n";
import { apiErrorMessage } from "@/lib/api";
import { joinList, splitLocations } from "@/lib/format";
import { resolveSelection } from "@/lib/locations";
import { BOUNDS } from "@/lib/bounds";
import { allValidNumbers } from "@/lib/validate";

interface Econ {
  trial_hours: number;
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  reward_pwa_mb: number;
  reward_push_mb: number;
  reward_streak_mb: number;
  streak_days: number;
}

const DEFAULT_ECON: Econ = {
  trial_hours: 24,
  daily_limit_mb: 1024,
  referral_reward_mb: 500,
  referral_reward_limit: 10,
  reward_pwa_mb: 200,
  reward_push_mb: 200,
  reward_streak_mb: 200,
  streak_days: 3,
};

export function SiteSetup() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { data: squads, isLoading, isError } = useSquads();
  // pre-fill so re-running never clobbers live values; must LOAD before the form is usable, or a
  // submit would POST DEFAULT_ECON over the live economy on a failed GET (H1).
  const { data: current, isError: settingsError, refetch: refetchSettings } = useSiteSettings();
  const complete = useCompleteSiteSetup();
  const [trialSquad, setTrialSquad] = useState("");
  const [econ, setEcon] = useState<Econ>(DEFAULT_ECON);
  const [locations, setLocations] = useState<string[]>([]);
  const [locationsText, setLocationsText] = useState("");
  const derivable = useSiteDerivableLocations(trialSquad);
  const hydrated = useRef(false);

  // Hydrate ONCE from current site settings (safe re-run). A ref guard stops a later cache write
  // from resetting in-progress edits (mirrors SiteSettings).
  useEffect(() => {
    if (current && !hydrated.current) {
      hydrated.current = true;
      setEcon({
        trial_hours: current.trial_hours,
        daily_limit_mb: current.daily_limit_mb,
        referral_reward_mb: current.referral_reward_mb,
        referral_reward_limit: current.referral_reward_limit,
        reward_pwa_mb: current.reward_pwa_mb,
        reward_push_mb: current.reward_push_mb,
        reward_streak_mb: current.reward_streak_mb,
        streak_days: current.streak_days,
      });
      if (current.locations.length > 0) {
        setLocations(current.locations);
        setLocationsText(joinList(current.locations));
      }
    }
  }, [current]);

  // The saved squad is only kept if the panel still has it. A deleted one used to stay in state
  // while the select — which has no option for it — showed the first live squad, so the form read
  // one squad and saved another, and the site could no longer provision anyone.
  const savedSquad = current?.trial_squad ?? "";
  const squadGone = Boolean(savedSquad && squads && !squads.some((s) => s.uuid === savedSquad));
  useEffect(() => {
    if (trialSquad || !current) return;
    if (squads) {
      if (savedSquad && !squadGone) {
        setTrialSquad(savedSquad);
      } else if (squads.length > 0) {
        setTrialSquad(squads[0].uuid);
        // Locations saved for a squad that is gone mean nothing for this one.
        setLocations([]);
        setLocationsText("");
      }
    } else if (isError && savedSquad) {
      setTrialSquad(savedSquad); // the panel cannot be asked; keep what was saved
    }
  }, [squads, isError, current, savedSquad, squadGone, trialSquad]);

  // Don't render the form until current settings load — otherwise DEFAULT_ECON could be saved over
  // a customised live economy on a failed GET (H1).
  if (!current) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("ssu.title")}>
          <SiteTabs />
        </PageHeader>
        {settingsError ? (
          <ErrorState onRetry={() => refetchSettings()} />
        ) : (
          <Card className="max-w-2xl">
            <div className="flex justify-center py-16">
              <Spinner className="h-8 w-8 text-brand" />
            </div>
          </Card>
        )}
      </div>
    );
  }

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
        { value: econ.trial_hours, ...BOUNDS.trialHours },
        { value: econ.daily_limit_mb, ...BOUNDS.dailyLimitMb },
        { value: econ.referral_reward_mb, ...BOUNDS.rewardMb },
        { value: econ.referral_reward_limit, ...BOUNDS.rewardLimit },
        { value: econ.reward_pwa_mb, ...BOUNDS.rewardMb },
        { value: econ.reward_push_mb, ...BOUNDS.rewardMb },
        { value: econ.reward_streak_mb, ...BOUNDS.rewardMb },
        { value: econ.streak_days, ...BOUNDS.streakDays },
      ])
    ) {
      toast.error(t("set.invalidNumbers"));
      return;
    }
    complete.mutate(
      {
        trial_squad: trialSquad,
        // Never a name the squad stopped serving: those are shown in the picker, then dropped.
        locations: pickerUnavailable
          ? splitLocations(locationsText)
          : resolveSelection(locations, picker ?? []).save,
        ...econ,
      },
      {
        onSuccess: () => {
          toast.success(t("ssu.done"));
          navigate("/site/settings", { replace: true });
        },
        // The server rejects a location the squad doesn't serve — say WHICH one.
        onError: (err) => toast.error(apiErrorMessage(err, t("ss.saveFailed"))),
      },
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("ssu.title")}
        sub={t("ssu.sub")}
        actions={
          <Button
            type="submit"
            form="site-setup"
            loading={complete.isPending}
            disabled={!trialSquad}
          >
            {t("ssu.submit")}
          </Button>
        }
      >
        <SiteTabs />
      </PageHeader>

      <form id="site-setup" onSubmit={submit} className="space-y-6">
        <Card className="max-w-2xl">
          <CardHeader title={t("ssu.squad")} icon={Server} />
          {squadGone && (
            <p
              role="status"
              className="mb-3 flex items-start gap-2 rounded-xl bg-warning-500/15 p-2.5 text-xs text-warning-700"
            >
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              {t("ssu.squadGone")}
            </p>
          )}
          <Field label={t("ssu.squad.field")}>
            {isLoading ? (
              <Spinner className="h-5 w-5 text-brand" />
            ) : isError ? (
              <ErrorState compact message={t("setup.squadsUnreachable")} />
            ) : (
              <Select
                value={trialSquad}
                onChange={(e) => {
                  setTrialSquad(e.target.value);
                  // A new squad has its own locations; clearing means "derive them all".
                  setLocations([]);
                  setLocationsText("");
                }}
              >
                {(squads ?? []).map((s) => (
                  <option key={s.uuid} value={s.uuid}>
                    {s.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </Card>

        <Card className="max-w-2xl">
          <CardHeader title={t("ss.economy")} icon={Coins} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("set.trialHours")}>
              <NumberInput
                {...BOUNDS.trialHours}
                value={econ.trial_hours}
                onChange={setNum("trial_hours")}
              />
            </Field>
            <Field label={t("set.dailyLimit")}>
              <NumberInput
                {...BOUNDS.dailyLimitMb}
                value={econ.daily_limit_mb}
                onChange={setNum("daily_limit_mb")}
              />
            </Field>
          </div>
        </Card>

        <Card className="max-w-2xl">
          <CardHeader title={t("ss.rewards")} icon={Gift} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("set.rewardMb")}>
              <NumberInput
                {...BOUNDS.rewardMb}
                value={econ.referral_reward_mb}
                onChange={setNum("referral_reward_mb")}
              />
            </Field>
            <Field label={t("set.rewardLimit")}>
              <NumberInput
                {...BOUNDS.rewardLimit}
                value={econ.referral_reward_limit}
                onChange={setNum("referral_reward_limit")}
              />
            </Field>
            <Field label={t("ss.reward.pwa")}>
              <NumberInput
                {...BOUNDS.rewardMb}
                value={econ.reward_pwa_mb}
                onChange={setNum("reward_pwa_mb")}
              />
            </Field>
            <Field label={t("ss.reward.push")}>
              <NumberInput
                {...BOUNDS.rewardMb}
                value={econ.reward_push_mb}
                onChange={setNum("reward_push_mb")}
              />
            </Field>
            <Field label={t("ss.reward.streak")}>
              <NumberInput
                {...BOUNDS.rewardMb}
                value={econ.reward_streak_mb}
                onChange={setNum("reward_streak_mb")}
              />
            </Field>
            <Field label={t("ss.reward.streakDays")}>
              <NumberInput
                {...BOUNDS.streakDays}
                value={econ.streak_days}
                onChange={setNum("streak_days")}
              />
            </Field>
          </div>
        </Card>

        <Card className="max-w-2xl">
          <CardHeader title={t("ss.locations")} sub={t("ssu.locations.sub")} icon={MapPin} />
          <LocationPicker
            available={picker}
            loading={derivable.isLoading}
            unavailable={pickerUnavailable}
            selected={locations}
            onChange={setLocations}
            fallbackText={locationsText}
            onFallbackTextChange={setLocationsText}
          />
        </Card>
      </form>
    </div>
  );
}
