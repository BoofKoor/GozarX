import { type ChangeEvent, type FormEvent, type ReactNode, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/ui/Spinner";
import { useSettings, useUpdateSettings } from "@/hooks/useSettings";
import { splitLocations } from "@/lib/format";

interface FormState {
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  trial_hours: number;
  ads_enabled: boolean;
  locations: string;
}

type NumKey = "daily_limit_mb" | "referral_reward_mb" | "referral_reward_limit" | "trial_hours";

const EMPTY: FormState = {
  daily_limit_mb: 1024,
  referral_reward_mb: 500,
  referral_reward_limit: 10,
  trial_hours: 24,
  ads_enabled: false,
  locations: "",
};

export function Settings() {
  const { data, isLoading } = useSettings();
  const update = useUpdateSettings();
  const [form, setForm] = useState<FormState>(EMPTY);

  useEffect(() => {
    if (data) {
      setForm({
        daily_limit_mb: data.daily_limit_mb,
        referral_reward_mb: data.referral_reward_mb,
        referral_reward_limit: data.referral_reward_limit,
        trial_hours: data.trial_hours,
        ads_enabled: data.ads_enabled,
        locations: data.locations.join("، "),
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

  const setNum = (key: NumKey) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: Number(e.target.value) }));

  function submit(e: FormEvent) {
    e.preventDefault();
    update.mutate(
      {
        daily_limit_mb: form.daily_limit_mb,
        referral_reward_mb: form.referral_reward_mb,
        referral_reward_limit: form.referral_reward_limit,
        trial_hours: form.trial_hours,
        ads_enabled: form.ads_enabled,
        locations: splitLocations(form.locations),
      },
      {
        onSuccess: () => toast.success("تنظیمات ذخیره شد."),
        onError: () => toast.error("ذخیره نشد."),
      },
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">تنظیمات</h1>
      <Card className="max-w-xl">
        <form onSubmit={submit} className="space-y-4">
          <Labeled label="حجم روزانه (مگابایت)">
            <Input type="number" value={form.daily_limit_mb} onChange={setNum("daily_limit_mb")} />
          </Labeled>
          <Labeled label="پاداش هر دعوت (مگابایت)">
            <Input
              type="number"
              value={form.referral_reward_mb}
              onChange={setNum("referral_reward_mb")}
            />
          </Labeled>
          <Labeled label="سقف دعوت‌های پاداش‌دار">
            <Input
              type="number"
              value={form.referral_reward_limit}
              onChange={setNum("referral_reward_limit")}
            />
          </Labeled>
          <Labeled label="مدت اعتبار کانفیگ (ساعت)">
            <Input type="number" value={form.trial_hours} onChange={setNum("trial_hours")} />
          </Labeled>
          <Labeled label="لوکیشن‌ها (با کاما جدا کنید؛ خالی = همه)">
            <Input
              value={form.locations}
              onChange={(e) => setForm((f) => ({ ...f, locations: e.target.value }))}
              placeholder="مثال: آلمان، هلند"
            />
          </Labeled>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.ads_enabled}
              onChange={(e) => setForm((f) => ({ ...f, ads_enabled: e.target.checked }))}
              className="h-4 w-4 accent-brand"
            />
            نمایش پیام تبلیغاتی پس از دریافت کانفیگ
          </label>
          <Button type="submit" loading={update.isPending}>
            ذخیره
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
