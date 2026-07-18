import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { NumberInput } from "@/components/ui/NumberInput";
import { Spinner } from "@/components/ui/Spinner";
import { useSettings, useUpdateSettings } from "@/hooks/useSettings";
import { splitLocations } from "@/lib/format";
import { allValidNumbers } from "@/lib/validate";

interface FormState {
  daily_limit_mb: number;
  referral_reward_mb: number;
  referral_reward_limit: number;
  trial_hours: number;
  configs_per_page: number;
  ads_enabled: boolean;
  locations: string;
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
  locations: "",
  ad_button_enabled: false,
  ad_button_text: "",
  ad_button_url: "",
  ad_button_emoji_id: "",
};

export function Settings() {
  const { data, isError, refetch } = useSettings();
  const update = useUpdateSettings();
  const [form, setForm] = useState<FormState>(EMPTY);

  useEffect(() => {
    if (data) {
      setForm({
        daily_limit_mb: data.daily_limit_mb,
        referral_reward_mb: data.referral_reward_mb,
        referral_reward_limit: data.referral_reward_limit,
        trial_hours: data.trial_hours,
        configs_per_page: data.configs_per_page,
        ads_enabled: data.ads_enabled,
        locations: data.locations.join("، "),
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
        <h1 className="text-xl font-bold">تنظیمات</h1>
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
      toast.error("مقادیر عددی نامعتبرند. لطفاً همهٔ فیلدها را پر کنید.");
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
        locations: splitLocations(form.locations),
        ad_button_enabled: form.ad_button_enabled,
        ad_button_text: form.ad_button_text.trim(),
        ad_button_url: form.ad_button_url.trim(),
        ad_button_emoji_id: form.ad_button_emoji_id.trim(),
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
            <NumberInput min={1} value={form.daily_limit_mb} onChange={setNum("daily_limit_mb")} />
          </Labeled>
          <Labeled label="پاداش هر دعوت (مگابایت)">
            <NumberInput
              min={0}
              value={form.referral_reward_mb}
              onChange={setNum("referral_reward_mb")}
            />
          </Labeled>
          <Labeled label="سقف دعوت‌های پاداش‌دار">
            <NumberInput
              min={0}
              value={form.referral_reward_limit}
              onChange={setNum("referral_reward_limit")}
            />
          </Labeled>
          <Labeled label="مدت اعتبار کانفیگ (ساعت)">
            <NumberInput min={1} value={form.trial_hours} onChange={setNum("trial_hours")} />
          </Labeled>
          <Labeled label="تعداد کانفیگ در هر صفحهٔ منو">
            <NumberInput
              min={1}
              value={form.configs_per_page}
              onChange={setNum("configs_per_page")}
            />
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

          <div className="space-y-4 border-t border-slate-200 pt-4 dark:border-slate-700">
            <div>
              <h2 className="text-sm font-bold text-slate-600 dark:text-slate-300">
                دکمهٔ تبلیغ (فقط فارسی)
              </h2>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                کنار دکمهٔ «تغییر لوکیشن» در صفحهٔ کانفیگ نمایش داده می‌شود.
              </p>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.ad_button_enabled}
                onChange={(e) => setForm((f) => ({ ...f, ad_button_enabled: e.target.checked }))}
                className="h-4 w-4 accent-brand"
              />
              نمایش دکمهٔ تبلیغ
            </label>
            <Labeled label="متن دکمه">
              <Input
                value={form.ad_button_text}
                onChange={(e) => setForm((f) => ({ ...f, ad_button_text: e.target.value }))}
                placeholder="مثال: کانال ما"
              />
            </Labeled>
            <Labeled label="لینک دکمه (https:// یا tg://)">
              <Input
                dir="ltr"
                value={form.ad_button_url}
                onChange={(e) => setForm((f) => ({ ...f, ad_button_url: e.target.value }))}
                placeholder="https://t.me/example"
              />
            </Labeled>
            <Labeled label="آی‌دی ایموجی پریمیوم (اختیاری)">
              <Input
                dir="ltr"
                value={form.ad_button_emoji_id}
                onChange={(e) => setForm((f) => ({ ...f, ad_button_emoji_id: e.target.value }))}
                placeholder="مثال: 5368324170671202286"
              />
            </Labeled>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              ایموجی پریمیوم فقط وقتی نمایش داده می‌شود که مالک ربات اشتراک تلگرام پریمیوم فعال
              داشته باشد؛ در غیر این‌صورت دکمه بدون ایموجی نشان داده می‌شود.
            </p>
          </div>

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
