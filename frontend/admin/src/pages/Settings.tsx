import { Coins, MapPin, Megaphone, Save } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { NumberInput } from "@/components/ui/NumberInput";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { Switch } from "@/components/ui/Switch";
import { LocationPicker } from "@/components/site/LocationPicker";
import { useSettings, useUpdateSettings } from "@/hooks/useSettings";
import { useSiteDerivableLocations } from "@/hooks/useSite";
import { useI18n } from "@/i18n";
import { apiErrorMessage } from "@/lib/api";
import { splitLocations } from "@/lib/format";
import { allValidNumbers } from "@/lib/validate";

interface FormState {
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  trial_hours: number;
  configs_per_page: number;
  ads_enabled: boolean;
  locations: string[];
  /** Only used when the squad list cannot be fetched. */
  locationsText: string;
  ad_button_enabled: boolean;
  ad_button_text: string;
  ad_button_url: string;
  ad_button_emoji_id: string;
}

type NumKey =
  | "daily_limit_mb"
  | "referral_reward_mb"
  | "referral_reward_limit"
  | "trial_hours"
  | "configs_per_page";

const EMPTY: FormState = {
  daily_limit_mb: 1024,
  referral_reward_mb: 500,
  referral_reward_limit: 10,
  trial_hours: 24,
  configs_per_page: 8,
  ads_enabled: false,
  locations: [],
  locationsText: "",
  ad_button_enabled: false,
  ad_button_text: "",
  ad_button_url: "",
  ad_button_emoji_id: "",
};

export function Settings() {
  const { t } = useI18n();
  const { data, isError, refetch } = useSettings();
  const update = useUpdateSettings();
  const [form, setForm] = useState<FormState>(EMPTY);
  // The bot's own trial squad decides which location names are valid here — the same endpoint the
  // website forms use, just pointed at a different squad.
  const derivable = useSiteDerivableLocations(data?.trial_squad ?? "");

  useEffect(() => {
    if (data) {
      setForm({
        daily_limit_mb: data.daily_limit_mb,
        referral_reward_mb: data.referral_reward_mb,
        referral_reward_limit: data.referral_reward_limit,
        trial_hours: data.trial_hours,
        configs_per_page: data.configs_per_page,
        ads_enabled: data.ads_enabled,
        locations: data.locations,
        locationsText: data.locations.join("، "),
        ad_button_enabled: data.ad_button_enabled,
        ad_button_text: data.ad_button_text,
        ad_button_url: data.ad_button_url,
        ad_button_emoji_id: data.ad_button_emoji_id,
      });
    }
  }, [data]);

  // Guard on "no usable data" — never fall through to the EMPTY-seeded form on a failed GET, or a
  // save would PUT hardcoded defaults over the live economy (H1). A stale-but-present cache still
  // renders the form; only a truly empty load shows the spinner/error.
  if (!data) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("set.title")} />
        {isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : (
          <div className="flex justify-center py-20">
            <Spinner className="h-8 w-8 text-brand" />
          </div>
        )}
      </div>
    );
  }

  const setNum = (key: NumKey) => (n: number) => setForm((f) => ({ ...f, [key]: n }));
  const picker = derivable.data;
  const pickerUnavailable = derivable.isError || (!derivable.isLoading && !picker);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (
      !allValidNumbers([
        { value: form.daily_limit_mb, min: 1 },
        { value: form.referral_reward_mb, min: 0 },
        { value: form.referral_reward_limit, min: 0 },
        { value: form.trial_hours, min: 1 },
        { value: form.configs_per_page, min: 1 },
      ])
    ) {
      toast.error(t("set.invalidNumbers"));
      return;
    }
    update.mutate(
      {
        daily_limit_mb: form.daily_limit_mb,
        referral_reward_mb: form.referral_reward_mb,
        referral_reward_limit: form.referral_reward_limit,
        trial_hours: form.trial_hours,
        configs_per_page: form.configs_per_page,
        ads_enabled: form.ads_enabled,
        locations: pickerUnavailable ? splitLocations(form.locationsText) : form.locations,
        ad_button_enabled: form.ad_button_enabled,
        ad_button_text: form.ad_button_text.trim(),
        ad_button_url: form.ad_button_url.trim(),
        ad_button_emoji_id: form.ad_button_emoji_id.trim(),
      },
      {
        onSuccess: () => toast.success(t("set.saved")),
        // Surface the server's own reason — a 400 naming a location the squad does not serve is
        // actionable; one generic "could not save" is not.
        onError: (err) => toast.error(apiErrorMessage(err, t("set.saveFailed"))),
      },
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("set.title")}
        sub={t("set.sub")}
        actions={
          <Button type="submit" form="bot-settings" loading={update.isPending}>
            <Save className="h-4 w-4" />
            {t("set.save")}
          </Button>
        }
      />

      {/* The economy card spans, then the two behaviour cards tile: three stacked max-w-2xl cards
          left the right half of a console screen empty. */}
      <form id="bot-settings" onSubmit={submit} className="grid gap-4 xl:grid-cols-2">
        <Card className="xl:col-span-2">
          <CardHeader title={t("set.economy")} sub={t("set.economy.sub")} icon={Coins} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("set.dailyLimit")}>
              <NumberInput
                min={1}
                value={form.daily_limit_mb}
                onChange={setNum("daily_limit_mb")}
              />
            </Field>
            <Field label={t("set.trialHours")}>
              <NumberInput min={1} value={form.trial_hours} onChange={setNum("trial_hours")} />
            </Field>
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
          </div>
        </Card>

        <Card>
          <CardHeader title={t("set.menu")} icon={MapPin} />
          <div className="space-y-4">
            <Field label={t("set.perPage")}>
              <NumberInput
                min={1}
                value={form.configs_per_page}
                onChange={setNum("configs_per_page")}
              />
            </Field>
            <Field label={t("set.locations")} hint={t("set.locations.hint")}>
              {/* The same validated picker the website forms use, pointed at the BOT's squad. A
                  free-text box here could store a name the squad does not serve, and the bot then
                  matches it against no remark at all. */}
              <LocationPicker
                available={picker}
                loading={derivable.isLoading}
                unavailable={pickerUnavailable}
                selected={form.locations}
                onChange={(next) => setForm((f) => ({ ...f, locations: next }))}
                fallbackText={form.locationsText}
                onFallbackTextChange={(v) => setForm((f) => ({ ...f, locationsText: v }))}
              />
            </Field>
            <Switch
              checked={form.ads_enabled}
              onChange={(v) => setForm((f) => ({ ...f, ads_enabled: v }))}
              label={t("set.ads")}
            />
          </div>
        </Card>

        <Card>
          <CardHeader title={t("set.adButton")} sub={t("set.adButton.sub")} icon={Megaphone} />
          <div className="space-y-4">
            <Switch
              checked={form.ad_button_enabled}
              onChange={(v) => setForm((f) => ({ ...f, ad_button_enabled: v }))}
              label={t("set.adButton.enabled")}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("set.adButton.text")}>
                <Input
                  value={form.ad_button_text}
                  onChange={(e) => setForm((f) => ({ ...f, ad_button_text: e.target.value }))}
                  placeholder={t("set.adButton.textPlaceholder")}
                />
              </Field>
              <Field label={t("set.adButton.url")}>
                <Input
                  dir="ltr"
                  value={form.ad_button_url}
                  onChange={(e) => setForm((f) => ({ ...f, ad_button_url: e.target.value }))}
                  placeholder="https://t.me/example"
                />
              </Field>
            </div>
            <Field label={t("set.adButton.emoji")} hint={t("set.adButton.emojiHint")}>
              <Input
                dir="ltr"
                value={form.ad_button_emoji_id}
                onChange={(e) => setForm((f) => ({ ...f, ad_button_emoji_id: e.target.value }))}
                placeholder="مثال: 5368324170671202286"
              />
            </Field>
          </div>
        </Card>
      </form>
    </div>
  );
}
