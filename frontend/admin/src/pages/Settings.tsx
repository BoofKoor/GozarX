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
        <PageHeader title="تنظیمات ربات" />
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
      <PageHeader
        title="تنظیمات ربات"
        sub="اقتصاد و رفتار ربات تلگرام. تغییرات بلافاصله اعمال می‌شوند و نیازی به دیپلوی ندارند."
        actions={
          <Button type="submit" form="bot-settings" loading={update.isPending}>
            <Save className="h-4 w-4" />
            ذخیره
          </Button>
        }
      />

      <form id="bot-settings" onSubmit={submit} className="space-y-6">
        <Card className="max-w-2xl">
          <CardHeader
            title="اقتصاد"
            sub="حجم روزانه، پاداش دعوت و مدت اعتبار کانفیگ"
            icon={Coins}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="حجم روزانه (مگابایت)">
              <NumberInput
                min={1}
                value={form.daily_limit_mb}
                onChange={setNum("daily_limit_mb")}
              />
            </Field>
            <Field label="مدت اعتبار کانفیگ (ساعت)">
              <NumberInput min={1} value={form.trial_hours} onChange={setNum("trial_hours")} />
            </Field>
            <Field label="پاداش هر دعوت (مگابایت)">
              <NumberInput
                min={0}
                value={form.referral_reward_mb}
                onChange={setNum("referral_reward_mb")}
              />
            </Field>
            <Field
              label="سقف دعوت‌های پاداش‌دار"
              hint="بعد از این تعداد، دعوت تازه پاداشی اضافه نمی‌کند."
            >
              <NumberInput
                min={0}
                value={form.referral_reward_limit}
                onChange={setNum("referral_reward_limit")}
              />
            </Field>
          </div>
        </Card>

        <Card className="max-w-2xl">
          <CardHeader title="منو و لوکیشن‌ها" icon={MapPin} />
          <div className="space-y-4">
            <Field label="تعداد کانفیگ در هر صفحهٔ منو">
              <NumberInput
                min={1}
                value={form.configs_per_page}
                onChange={setNum("configs_per_page")}
              />
            </Field>
            <Field label="لوکیشن‌ها" hint="با کاما جدا کنید؛ خالی یعنی همهٔ لوکیشن‌های اسکواد.">
              <Input
                value={form.locations}
                onChange={(e) => setForm((f) => ({ ...f, locations: e.target.value }))}
                placeholder="مثال: آلمان، هلند"
              />
            </Field>
            <Switch
              checked={form.ads_enabled}
              onChange={(v) => setForm((f) => ({ ...f, ads_enabled: v }))}
              label="نمایش پیام تبلیغاتی پس از دریافت کانفیگ"
            />
          </div>
        </Card>

        <Card className="max-w-2xl">
          <CardHeader
            title="دکمهٔ تبلیغ (فقط فارسی)"
            sub="کنار دکمهٔ «تغییر لوکیشن» در صفحهٔ کانفیگ نمایش داده می‌شود."
            icon={Megaphone}
          />
          <div className="space-y-4">
            <Switch
              checked={form.ad_button_enabled}
              onChange={(v) => setForm((f) => ({ ...f, ad_button_enabled: v }))}
              label="نمایش دکمهٔ تبلیغ"
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="متن دکمه">
                <Input
                  value={form.ad_button_text}
                  onChange={(e) => setForm((f) => ({ ...f, ad_button_text: e.target.value }))}
                  placeholder="مثال: کانال ما"
                />
              </Field>
              <Field label="لینک دکمه">
                <Input
                  dir="ltr"
                  value={form.ad_button_url}
                  onChange={(e) => setForm((f) => ({ ...f, ad_button_url: e.target.value }))}
                  placeholder="https://t.me/example"
                />
              </Field>
            </div>
            <Field
              label="آی‌دی ایموجی پریمیوم (اختیاری)"
              hint="فقط وقتی نمایش داده می‌شود که مالک ربات اشتراک تلگرام پریمیوم فعال داشته باشد؛ در غیر این‌صورت دکمه بدون ایموجی نشان داده می‌شود."
            >
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
