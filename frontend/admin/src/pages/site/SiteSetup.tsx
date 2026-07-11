import { type ChangeEvent, type FormEvent, type ReactNode, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/ui/Spinner";
import { useSquads } from "@/hooks/useSetup";
import {
  useCompleteSiteSetup,
  useSiteDerivableLocations,
  useSiteSettings,
} from "@/hooks/useSite";
import { splitLocations } from "@/lib/format";

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
  const { data: current } = useSiteSettings(); // pre-fill so re-running never clobbers live values
  const complete = useCompleteSiteSetup();
  const [trialSquad, setTrialSquad] = useState("");
  const [econ, setEcon] = useState<Econ>(DEFAULT_ECON);
  const [locations, setLocations] = useState("");
  const { data: derivable } = useSiteDerivableLocations(trialSquad);

  // Hydrate from current site settings on first load (safe re-run); default the squad otherwise.
  useEffect(() => {
    if (current) {
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

  const setNum = (key: keyof Econ) => (e: ChangeEvent<HTMLInputElement>) =>
    setEcon((s) => ({ ...s, [key]: Number(e.target.value) }));

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!trialSquad) {
      toast.error("یک اسکواد انتخاب کنید.");
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
      <h1 className="text-xl font-bold">راه‌اندازی وب‌سایت</h1>
      <Card className="max-w-xl">
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
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
                onChange={(e) => setTrialSquad(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand dark:border-slate-700 dark:bg-slate-900"
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
              <Input type="number" min={1} value={econ.trial_hours} onChange={setNum("trial_hours")} />
            </Labeled>
            <Labeled label="حجم روزانه (مگابایت)">
              <Input type="number" value={econ.daily_limit_mb} onChange={setNum("daily_limit_mb")} />
            </Labeled>
            <Labeled label="پاداش هر دعوت (مگابایت)">
              <Input
                type="number"
                value={econ.referral_reward_mb}
                onChange={setNum("referral_reward_mb")}
              />
            </Labeled>
            <Labeled label="سقف دعوت‌های پاداش‌دار">
              <Input
                type="number"
                value={econ.referral_reward_limit}
                onChange={setNum("referral_reward_limit")}
              />
            </Labeled>
            <Labeled label="پاداش نصب اپ / PWA (مگابایت)">
              <Input type="number" value={econ.reward_pwa_mb} onChange={setNum("reward_pwa_mb")} />
            </Labeled>
            <Labeled label="پاداش فعال‌کردن اعلان (مگابایت)">
              <Input type="number" value={econ.reward_push_mb} onChange={setNum("reward_push_mb")} />
            </Labeled>
            <Labeled label="پاداش استریک (مگابایت)">
              <Input
                type="number"
                value={econ.reward_streak_mb}
                onChange={setNum("reward_streak_mb")}
              />
            </Labeled>
            <Labeled label="روزهای لازم برای استریک">
              <Input type="number" value={econ.streak_days} onChange={setNum("streak_days")} />
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
            <p className="text-xs text-slate-400">لوکیشن‌های این اسکواد: {derivable.join("، ")}</p>
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
