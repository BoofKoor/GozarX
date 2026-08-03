import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { NumberInput } from "@/components/ui/NumberInput";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { useSquads } from "@/hooks/useSetup";
import { useCompleteSiteSetup, useSiteDerivableLocations, useSiteSettings } from "@/hooks/useSite";
import { splitLocations } from "@/lib/format";
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
  const navigate = useNavigate();
  const { data: squads, isLoading, isError } = useSquads();
  // pre-fill so re-running never clobbers live values; must LOAD before the form is usable, or a
  // submit would POST DEFAULT_ECON over the live economy on a failed GET (H1).
  const { data: current, isError: settingsError, refetch: refetchSettings } = useSiteSettings();
  const complete = useCompleteSiteSetup();
  const [trialSquad, setTrialSquad] = useState("");
  const [econ, setEcon] = useState<Econ>(DEFAULT_ECON);
  const [locations, setLocations] = useState("");
  const { data: derivable } = useSiteDerivableLocations(trialSquad);
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
      if (current.locations.length > 0) setLocations(current.locations.join("، "));
    }
  }, [current]);

  useEffect(() => {
    if (trialSquad) return;
    if (current?.trial_squad) setTrialSquad(current.trial_squad);
    else if (squads && squads.length > 0) setTrialSquad(squads[0].uuid);
  }, [squads, current, trialSquad]);

  // Don't render the form until current settings load — otherwise DEFAULT_ECON could be saved over
  // a customised live economy on a failed GET (H1).
  if (!current) {
    return (
      <div className="space-y-6">
        <PageHeader title="راه‌اندازی وب‌سایت" />
        {settingsError ? (
          <ErrorState onRetry={() => refetchSettings()} />
        ) : (
          <Card className="max-w-xl">
            <div className="flex justify-center py-16">
              <Spinner className="h-8 w-8 text-brand" />
            </div>
          </Card>
        )}
      </div>
    );
  }

  const setNum = (key: keyof Econ) => (n: number) => setEcon((s) => ({ ...s, [key]: n }));

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!trialSquad) {
      toast.error("یک اسکواد انتخاب کنید.");
      return;
    }
    if (
      !allValidNumbers([
        { value: econ.trial_hours, min: 1 },
        { value: econ.daily_limit_mb, min: 1 },
        { value: econ.referral_reward_mb, min: 0 },
        { value: econ.referral_reward_limit, min: 0 },
        { value: econ.reward_pwa_mb, min: 0 },
        { value: econ.reward_push_mb, min: 0 },
        { value: econ.reward_streak_mb, min: 0 },
        { value: econ.streak_days, min: 1 },
      ])
    ) {
      toast.error("مقادیر عددی نامعتبرند. لطفاً همهٔ فیلدها را پر کنید.");
      return;
    }
    complete.mutate(
      { trial_squad: trialSquad, locations: splitLocations(locations), ...econ },
      {
        onSuccess: () => {
          toast.success("راه‌اندازی وب‌سایت کامل شد.");
          navigate("/site/settings", { replace: true });
        },
        onError: () => toast.error("ذخیره نشد."),
      },
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="راه‌اندازی وب‌سایت" />
      <Card className="max-w-xl">
        <p className="mb-6 text-sm text-content-muted">
          اسکواد آزمایشی و اقتصاد وب‌سایت را تنظیم کنید. لوکیشن‌ها از روی نام remark همان اسکواد
          استخراج می‌شوند.
        </p>
        <form onSubmit={submit} className="space-y-4">
          <Labeled label="اسکواد آزمایشی وب‌سایت">
            {isLoading ? (
              <Spinner className="h-5 w-5 text-brand" />
            ) : isError ? (
              <div className="text-sm text-red-500">دریافت اسکوادها از پنل ممکن نشد.</div>
            ) : (
              <select
                value={trialSquad}
                onChange={(e) => {
                  setTrialSquad(e.target.value);
                  setLocations(""); // a new squad has its own locations; empty => derive them all
                }}
                className="field-control"
              >
                {(squads ?? []).map((s) => (
                  <option key={s.uuid} value={s.uuid}>
                    {s.name}
                  </option>
                ))}
              </select>
            )}
          </Labeled>
          <div className="grid gap-4 sm:grid-cols-2">
            <Labeled label="مدت اعتبار کانفیگ (ساعت)">
              <NumberInput min={1} value={econ.trial_hours} onChange={setNum("trial_hours")} />
            </Labeled>
            <Labeled label="حجم روزانه (مگابایت)">
              <NumberInput
                min={1}
                value={econ.daily_limit_mb}
                onChange={setNum("daily_limit_mb")}
              />
            </Labeled>
            <Labeled label="پاداش هر دعوت (مگابایت)">
              <NumberInput
                min={0}
                value={econ.referral_reward_mb}
                onChange={setNum("referral_reward_mb")}
              />
            </Labeled>
            <Labeled label="سقف دعوت‌های پاداش‌دار">
              <NumberInput
                min={0}
                value={econ.referral_reward_limit}
                onChange={setNum("referral_reward_limit")}
              />
            </Labeled>
            <Labeled label="پاداش نصب اپ / PWA (مگابایت)">
              <NumberInput min={0} value={econ.reward_pwa_mb} onChange={setNum("reward_pwa_mb")} />
            </Labeled>
            <Labeled label="پاداش فعال‌کردن اعلان (مگابایت)">
              <NumberInput
                min={0}
                value={econ.reward_push_mb}
                onChange={setNum("reward_push_mb")}
              />
            </Labeled>
            <Labeled label="پاداش استریک (مگابایت)">
              <NumberInput
                min={0}
                value={econ.reward_streak_mb}
                onChange={setNum("reward_streak_mb")}
              />
            </Labeled>
            <Labeled label="روزهای لازم برای استریک">
              <NumberInput min={1} value={econ.streak_days} onChange={setNum("streak_days")} />
            </Labeled>
          </div>
          <Labeled label="لوکیشن‌ها (با کاما جدا کنید؛ خالی = همهٔ لوکیشن‌های اسکواد)">
            <Input
              value={locations}
              onChange={(e) => setLocations(e.target.value)}
              placeholder="مثال: آلمان، هلند"
            />
          </Labeled>
          {derivable && derivable.length > 0 && (
            <p className="text-xs text-content-subtle">
              لوکیشن‌های این اسکواد: {derivable.join("، ")}
            </p>
          )}
          <Button type="submit" loading={complete.isPending} disabled={!trialSquad}>
            ذخیره و تکمیل
          </Button>
        </form>
      </Card>
    </div>
  );
}

function Labeled({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-sm">{label}</label>
      {children}
    </div>
  );
}
