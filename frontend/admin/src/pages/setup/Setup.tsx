import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { NumberInput } from "@/components/ui/NumberInput";
import { Spinner } from "@/components/ui/Spinner";
import { useCompleteSetup, useSetupStatus, useSquads } from "@/hooks/useSetup";
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

  const setNum = (key: keyof Econ) => (n: number) => setEcon((s) => ({ ...s, [key]: n }));

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!trialSquad) {
      toast.error("یک اسکواد انتخاب کنید.");
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
      toast.error("مقادیر عددی نامعتبرند. لطفاً همهٔ فیلدها را پر کنید.");
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
        <p className="mb-6 text-sm text-content-muted">
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
          <Labeled label="حجم روزانه (مگابایت)">
            <NumberInput min={1} value={econ.daily_limit_mb} onChange={setNum("daily_limit_mb")} />
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
          <Labeled label="مدت اعتبار کانفیگ (ساعت)">
            <NumberInput min={1} value={econ.trial_hours} onChange={setNum("trial_hours")} />
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
