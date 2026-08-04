import { Coins, Gift, MapPin, Save } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { LocationPicker } from "@/components/site/LocationPicker";
import { SiteTabs } from "@/components/site/SiteTabs";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Field } from "@/components/ui/Field";
import { NumberInput } from "@/components/ui/NumberInput";
import { PageHeader } from "@/components/ui/PageHeader";
import { Select } from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";
import {
  useRefreshSiteLocations,
  useSiteDerivableLocations,
  useSiteSettings,
  useUpdateSiteSettings,
} from "@/hooks/useSite";
import { useI18n } from "@/i18n";
import { apiErrorMessage } from "@/lib/api";
import { joinList, splitLocations } from "@/lib/format";
import { allValidNumbers } from "@/lib/validate";

interface FormState {
  trial_hours: number;
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  reward_pwa_mb: number;
  reward_push_mb: number;
  reward_streak_mb: number;
  streak_days: number;
  locations: string[];
  locationsText: string; // only used when the squad list can't be fetched
  popular_location: string;
}

type NumKey = keyof Omit<FormState, "locations" | "locationsText" | "popular_location">;

const EMPTY: FormState = {
  trial_hours: 24,
  daily_limit_mb: 1024,
  referral_reward_mb: 500,
  referral_reward_limit: 10,
  reward_pwa_mb: 200,
  reward_push_mb: 200,
  reward_streak_mb: 200,
  streak_days: 3,
  locations: [],
  locationsText: "",
  popular_location: "",
};

export function SiteSettings() {
  const { t } = useI18n();
  const { data, isLoading, isError, refetch } = useSiteSettings();
  const update = useUpdateSiteSettings();
  const refresh = useRefreshSiteLocations();
  const [form, setForm] = useState<FormState>(EMPTY);
  const hydrated = useRef(false);

  // The squad's real location names — what the picker offers.
  const derivable = useSiteDerivableLocations(data?.trial_squad ?? "");

  // Hydrate the form once from the server. Later cache writes (save / refresh-locations) must not
  // reset in-progress edits — refreshFromSquad applies just the new locations itself.
  useEffect(() => {
    if (data && !hydrated.current) {
      hydrated.current = true;
      setForm({
        trial_hours: data.trial_hours,
        daily_limit_mb: data.daily_limit_mb,
        referral_reward_mb: data.referral_reward_mb,
        referral_reward_limit: data.referral_reward_limit,
        reward_pwa_mb: data.reward_pwa_mb,
        reward_push_mb: data.reward_push_mb,
        reward_streak_mb: data.reward_streak_mb,
        streak_days: data.streak_days,
        locations: data.locations,
        locationsText: joinList(data.locations),
        popular_location: data.popular_location ?? "",
      });
    }
  }, [data]);

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-8 w-8 text-brand" />
      </div>
    );
  }

  if (isError && !data) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("ss.title")}>
          <SiteTabs />
        </PageHeader>
        <ErrorState message={t("ss.unreachable")} onRetry={() => refetch()} />
      </div>
    );
  }

  // Not set up yet — the economy has no squad, so the public site can't provision. Send to the wizard.
  if (!data?.trial_squad) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("ss.title")}>
          <SiteTabs />
        </PageHeader>
        <Card>
          <EmptyState
            icon={MapPin}
            title={t("ss.notSetUp")}
            message={t("ss.notSetUp.msg")}
            action={
              <Link to="/site/setup">
                <Button>{t("ssu.title")}</Button>
              </Link>
            }
          />
        </Card>
      </div>
    );
  }

  const setNum = (key: NumKey) => (n: number) => setForm((f) => ({ ...f, [key]: n }));
  const picker = derivable.data;
  const pickerUnavailable = derivable.isError || (!derivable.isLoading && !picker);
  // What the popular-location select may offer: whatever the form currently says is on the picker.
  const offered = pickerUnavailable
    ? splitLocations(form.locationsText)
    : form.locations.length > 0
      ? form.locations
      : (picker ?? []);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (
      !allValidNumbers([
        { value: form.trial_hours, min: 1 },
        { value: form.daily_limit_mb, min: 1 },
        { value: form.referral_reward_mb, min: 0 },
        { value: form.referral_reward_limit, min: 0 },
        { value: form.reward_pwa_mb, min: 0 },
        { value: form.reward_push_mb, min: 0 },
        { value: form.reward_streak_mb, min: 0 },
        { value: form.streak_days, min: 1 },
      ])
    ) {
      toast.error(t("set.invalidNumbers"));
      return;
    }
    update.mutate(
      {
        trial_hours: form.trial_hours,
        daily_limit_mb: form.daily_limit_mb,
        referral_reward_mb: form.referral_reward_mb,
        referral_reward_limit: form.referral_reward_limit,
        reward_pwa_mb: form.reward_pwa_mb,
        reward_push_mb: form.reward_push_mb,
        reward_streak_mb: form.reward_streak_mb,
        streak_days: form.streak_days,
        locations: pickerUnavailable ? splitLocations(form.locationsText) : form.locations,
        popular_location: form.popular_location,
      },
      {
        onSuccess: () => toast.success(t("ss.saved")),
        // Show the server's own reason (which location isn't served, panel unreachable, …) rather
        // than one generic "could not save" for every distinct failure.
        onError: (err) => toast.error(apiErrorMessage(err, t("ss.saveFailed"))),
      },
    );
  }

  function refreshFromSquad() {
    refresh.mutate(undefined, {
      onSuccess: (d) => {
        setForm((f) => ({
          ...f,
          locations: d.locations,
          locationsText: joinList(d.locations),
        }));
        derivable.refetch();
        toast.success(t("ss.locations.refreshed"));
      },
      onError: (err) => toast.error(apiErrorMessage(err, t("ss.locations.refreshFailed"))),
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("ss.title")}
        sub={t("ss.sub")}
        actions={
          <Button type="submit" form="site-settings" loading={update.isPending}>
            <Save className="h-4 w-4" />
            {t("ss.save")}
          </Button>
        }
      >
        <SiteTabs />
      </PageHeader>

      <form id="site-settings" onSubmit={submit} className="space-y-6">
        <Card className="max-w-2xl">
          <CardHeader title={t("ss.economy")} icon={Coins} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("set.trialHours")}>
              <NumberInput min={1} value={form.trial_hours} onChange={setNum("trial_hours")} />
            </Field>
            <Field label={t("set.dailyLimit")}>
              <NumberInput
                min={1}
                value={form.daily_limit_mb}
                onChange={setNum("daily_limit_mb")}
              />
            </Field>
          </div>
        </Card>

        <Card className="max-w-2xl">
          <CardHeader title={t("ss.rewards")} sub={t("ss.rewards.sub")} icon={Gift} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("set.rewardMb")}>
              <NumberInput
                min={0}
                value={form.referral_reward_mb}
                onChange={setNum("referral_reward_mb")}
              />
            </Field>
            <Field label={t("set.rewardLimit")} hint={t("set.rewardLimit.hint")}>
              <NumberInput
                min={0}
                value={form.referral_reward_limit}
                onChange={setNum("referral_reward_limit")}
              />
            </Field>
            <Field label={t("ss.reward.pwa")}>
              <NumberInput min={0} value={form.reward_pwa_mb} onChange={setNum("reward_pwa_mb")} />
            </Field>
            <Field label={t("ss.reward.push")}>
              <NumberInput
                min={0}
                value={form.reward_push_mb}
                onChange={setNum("reward_push_mb")}
              />
            </Field>
            <Field label={t("ss.reward.streak")}>
              <NumberInput
                min={0}
                value={form.reward_streak_mb}
                onChange={setNum("reward_streak_mb")}
              />
            </Field>
            <Field label={t("ss.reward.streakDays")}>
              <NumberInput min={1} value={form.streak_days} onChange={setNum("streak_days")} />
            </Field>
          </div>
        </Card>

        <Card className="max-w-2xl">
          <CardHeader
            title={t("ss.locations")}
            sub={t("ss.locations.sub")}
            icon={MapPin}
            action={
              <Link to="/site/setup" className="text-xs text-brand hover:underline">
                {t("ss.locations.changeSquad")}
              </Link>
            }
          />
          <div className="space-y-4">
            <LocationPicker
              available={picker}
              loading={derivable.isLoading}
              unavailable={pickerUnavailable}
              selected={form.locations}
              onChange={(next) => setForm((f) => ({ ...f, locations: next }))}
              fallbackText={form.locationsText}
              onFallbackTextChange={(v) => setForm((f) => ({ ...f, locationsText: v }))}
              onRefresh={refreshFromSquad}
              refreshing={refresh.isPending}
            />
            <Field label={t("ss.popular")} hint={t("ss.popular.hint")}>
              <Select
                value={form.popular_location}
                onChange={(e) => setForm((f) => ({ ...f, popular_location: e.target.value }))}
              >
                <option value="">{t("ss.popular.none")}</option>
                {offered.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </Card>
      </form>
    </div>
  );
}
