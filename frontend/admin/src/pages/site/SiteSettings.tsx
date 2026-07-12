import {
  type ChangeEvent,
  type FormEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Spinner } from "@/components/ui/Spinner";
import { useRefreshSiteLocations, useSiteSettings, useUpdateSiteSettings } from "@/hooks/useSite";
import { splitLocations } from "@/lib/format";

interface FormState {
  trial_hours: number;
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  reward_pwa_mb: number;
  reward_push_mb: number;
  reward_streak_mb: number;
  streak_days: number;
  locations: string;
  popular_location: string;
}

type NumKey = keyof Omit<FormState, "locations">;

const EMPTY: FormState = {
  trial_hours: 24,
  daily_limit_mb: 1024,
  referral_reward_mb: 500,
  referral_reward_limit: 10,
  reward_pwa_mb: 200,
  reward_push_mb: 200,
  reward_streak_mb: 200,
  streak_days: 3,
  locations: "",
  popular_location: "",
};

export function SiteSettings() {
  const { data, isLoading, isError } = useSiteSettings();
  const update = useUpdateSiteSettings();
  const refresh = useRefreshSiteLocations();
  const [form, setForm] = useState<FormState>(EMPTY);
  const hydrated = useRef(false);

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
        locations: data.locations.join("، "),
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

  if (isError) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-bold">وب‌سایت</h1>
        <SiteTabs />
        <Card className="max-w-xl">
          <p className="text-sm text-red-500">دریافت تنظیمات وب‌سایت از سرور ممکن نشد.</p>
        </Card>
      </div>
    );
  }

  // Not set up yet — the economy has no squad, so the public site can't provision. Send to the wizard.
  if (!data?.trial_squad) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-bold">وب‌سایت</h1>
        <SiteTabs />
        <Card className="max-w-xl">
          <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
            وب‌سایت هنوز راه‌اندازی نشده است. ابتدا اسکواد آزمایشی و اقتصاد آن را تنظیم کنید.
          </p>
          <Link
            to="/site/setup"
            className="inline-flex items-center justify-center rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-brand-600"
          >
            راه‌اندازی وب‌سایت
          </Link>
        </Card>
      </div>
    );
  }

  const setNum = (key: NumKey) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: Number(e.target.value) }));

  function submit(e: FormEvent) {
    e.preventDefault();
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
        locations: splitLocations(form.locations),
        popular_location: form.popular_location,
      },
      {
        onSuccess: () => toast.success("تنظیمات وب‌سایت ذخیره شد."),
        onError: () => toast.error("ذخیره نشد."),
      },
    );
  }

  function refreshFromSquad() {
    refresh.mutate(undefined, {
      onSuccess: (d) => {
        setForm((f) => ({ ...f, locations: d.locations.join("، ") }));
        toast.success("لوکیشن‌ها از اسکواد به‌روزرسانی شد.");
      },
      onError: () => toast.error("به‌روزرسانی لوکیشن‌ها ممکن نشد."),
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">تنظیمات وب‌سایت</h1>
        <Link to="/site/setup" className="text-sm text-brand hover:underline">
          تغییر اسکواد / راه‌اندازی مجدد
        </Link>
      </div>
      <SiteTabs />
      <Card className="max-w-xl">
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Labeled label="مدت اعتبار کانفیگ (ساعت)">
              <Input type="number" min={1} value={form.trial_hours} onChange={setNum("trial_hours")} />
            </Labeled>
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
            <Labeled label="پاداش نصب اپ / PWA (مگابایت)">
              <Input type="number" value={form.reward_pwa_mb} onChange={setNum("reward_pwa_mb")} />
            </Labeled>
            <Labeled label="پاداش فعال‌کردن اعلان (مگابایت)">
              <Input type="number" value={form.reward_push_mb} onChange={setNum("reward_push_mb")} />
            </Labeled>
            <Labeled label="پاداش استریک (مگابایت)">
              <Input
                type="number"
                value={form.reward_streak_mb}
                onChange={setNum("reward_streak_mb")}
              />
            </Labeled>
            <Labeled label="روزهای لازم برای استریک">
              <Input type="number" value={form.streak_days} onChange={setNum("streak_days")} />
            </Labeled>
          </div>
          <Labeled label="لوکیشن‌ها (با کاما جدا کنید؛ خالی = همهٔ لوکیشن‌های اسکواد)">
            <div className="flex gap-2">
              <div className="flex-1">
                <Input
                  value={form.locations}
                  onChange={(e) => setForm((f) => ({ ...f, locations: e.target.value }))}
                  placeholder="مثال: آلمان، هلند"
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                onClick={refreshFromSquad}
                loading={refresh.isPending}
              >
                از اسکواد
              </Button>
            </div>
          </Labeled>
          <Labeled label="لوکیشن محبوب (نشان ⭐ روی پیکر سایت)">
            <select
              value={form.popular_location}
              onChange={(e) => setForm((f) => ({ ...f, popular_location: e.target.value }))}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/30 dark:border-slate-700 dark:bg-slate-900"
            >
              <option value="">— بدون —</option>
              {Array.from(
                new Set([...splitLocations(form.locations), form.popular_location].filter(Boolean)),
              ).map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
          </Labeled>
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
