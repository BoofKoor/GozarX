import { type ChangeEvent, type FormEvent, type ReactNode, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/ui/Spinner";
import { useCompleteSetup, useSetupStatus, useSquads } from "@/hooks/useSetup";
import { splitLocations } from "@/lib/format";

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
  const navigate = useNavigate();
  const { data: status } = useSetupStatus();
  const { data: squads, isLoading, isError } = useSquads();
  const complete = useCompleteSetup();
  const [trialSquad, setTrialSquad] = useState("");
  const [econ, setEcon] = useState<Econ>(DEFAULT_ECON);
  const [locations, setLocations] = useState("");

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

  const setNum = (key: keyof Econ) => (e: ChangeEvent<HTMLInputElement>) =>
    setEcon((s) => ({ ...s, [key]: Number(e.target.value) }));

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!trialSquad) {
      toast.error("یک اسکواد انتخاب کنید.");
      return;
    }
    complete.mutate(
      {
        trial_squad: trialSquad,
        locations: splitLocations(locations),
        ...econ,
        ads_enabled: false,
      },
      {
        onSuccess: () => {
          toast.success("راه‌اندازی کامل شد.");
          navigate("/", { replace: true });
        },
        onError: () => toast.error("ذخیره نشد."),
      },
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <h1 className="mb-1 text-xl font-bold text-brand">راه‌اندازی اولیه</h1>
        <p className="mb-6 text-sm text-slate-500 dark:text-slate-400">
          اسکواد آزمایشی و مقادیر اولیهٔ سرویس را تنظیم کنید.
        </p>
        <form onSubmit={submit} className="space-y-4">
          <Labeled label="اسکواد آزمایشی">
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
          <Labeled label="مدت اعتبار کانفیگ (ساعت)">
            <Input type="number" value={econ.trial_hours} onChange={setNum("trial_hours")} />
          </Labeled>
          <Labeled label="لوکیشن‌ها (با کاما جدا کنید؛ خالی = همهٔ لوکیشن‌های اسکواد)">
            <Input
              value={locations}
              onChange={(e) => setLocations(e.target.value)}
              placeholder="مثال: آلمان، هلند"
            />
          </Labeled>
          <Button
            type="submit"
            loading={complete.isPending}
            disabled={!trialSquad}
            className="w-full"
          >
            تکمیل و ورود به پنل
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
