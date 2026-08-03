import { RotateCcw, Save, Search, Type } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { Textarea } from "@/components/ui/Textarea";
import { useSiteCopy, useUpdateSiteCopy } from "@/hooks/useSite";
import { apiErrorMessage } from "@/lib/api";
import type { SiteCopyItem } from "@/types/api";

const GROUP_LABELS: Record<string, { title: string; sub: string }> = {
  seo: { title: "متا و سئو", sub: "عنوان و توضیح صفحهٔ اصلی در نتایج گوگل" },
  hero: { title: "هدر اصلی", sub: "اولین چیزی که بازدیدکننده می‌بیند" },
  widget: { title: "ویجت دریافت کانفیگ", sub: "کادر گرفتن کانفیگ روی صفحهٔ اصلی" },
  sections: { title: "بخش‌های صفحهٔ اصلی", sub: "عنوان و زیرعنوان بخش‌های لوکیشن، اپ‌ها و سوالات" },
  push: {
    title: "متن اعلان‌های خودکار",
    sub: "پیام‌هایی که خود سرویس هنگام اتمام کانفیگ می‌فرستد",
  },
};

const GROUP_ORDER = ["seo", "hero", "widget", "sections", "push"];

/** Long-form keys get a textarea; the rest a single-line input. */
const MULTILINE = /(_sub|_description|_body)$/;

/**
 * The website's own copy, editable in one place.
 *
 * Only four site strings used to be editable, and they were buried among the bot's ~50 keys in
 * "متن‌ها" (with a Russian column the site has no use for). Everything else the visitor reads was a
 * compile-time constant. Each field shows the site's in-code default, so an empty box means "use
 * the default" rather than "show nothing" — clearing one is how you revert.
 */
export function SiteContent() {
  const { data, isLoading, isError, refetch } = useSiteCopy();
  const [filter, setFilter] = useState("");

  const groups = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const match = (item: SiteCopyItem) =>
      !needle ||
      item.key.toLowerCase().includes(needle) ||
      item.fa.toLowerCase().includes(needle) ||
      item.default_fa.toLowerCase().includes(needle);
    const byGroup = new Map<string, SiteCopyItem[]>();
    for (const item of data ?? []) {
      if (!match(item)) continue;
      byGroup.set(item.group, [...(byGroup.get(item.group) ?? []), item]);
    }
    return GROUP_ORDER.filter((g) => byGroup.has(g)).map((g) => ({
      group: g,
      items: byGroup.get(g)!,
    }));
  }, [data, filter]);

  const overridden = (data ?? []).filter((i) => i.overridden).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="محتوای وب‌سایت"
        sub="متن‌هایی که بازدیدکنندهٔ سایت می‌بیند. تغییرات بدون دیپلوی اعمال می‌شوند."
        actions={
          overridden > 0 ? <Badge tone="brand">{overridden} مورد سفارشی‌شده</Badge> : undefined
        }
      >
        <SiteTabs />
      </PageHeader>

      <div className="max-w-md">
        <Input
          aria-label="جستجو در متن‌ها"
          icon={<Search className="h-4 w-4" />}
          placeholder="جستجو در کلید یا متن…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      {isError && !data ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8 text-brand" />
        </div>
      ) : groups.length === 0 ? (
        <Card>
          <EmptyState icon={Type} title="متنی با این جستجو پیدا نشد" />
        </Card>
      ) : (
        groups.map(({ group, items }) => (
          <Card key={group}>
            <CardHeader
              title={GROUP_LABELS[group]?.title ?? group}
              sub={GROUP_LABELS[group]?.sub}
              icon={Type}
            />
            <div className="space-y-5">
              {items.map((item) => (
                <CopyEditor key={item.key} item={item} />
              ))}
            </div>
          </Card>
        ))
      )}
    </div>
  );
}

function CopyEditor({ item }: { item: SiteCopyItem }) {
  const update = useUpdateSiteCopy();
  const [fa, setFa] = useState(item.fa);
  const [en, setEn] = useState(item.en);
  const multiline = MULTILINE.test(item.key);
  const dirty = fa !== item.fa || en !== item.en;

  function save(nextFa = fa, nextEn = en) {
    update.mutate(
      { key: item.key, patch: { fa: nextFa, en: nextEn } },
      {
        onSuccess: (saved) => {
          setFa(saved.fa);
          setEn(saved.en);
          toast.success("ذخیره شد.");
        },
        onError: (err) => toast.error(apiErrorMessage(err, "ذخیره نشد.")),
      },
    );
  }

  function reset() {
    // Clearing both languages is what restores the site's own copy — the public endpoint treats a
    // blank row as "not overridden".
    setFa("");
    setEn("");
    save("", "");
  }

  const Control = multiline ? Textarea : Input;

  return (
    <div className="rounded-xl border border-line p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <code className="text-xs text-content-subtle" dir="ltr">
          {item.key}
        </code>
        <div className="flex items-center gap-1.5">
          {item.overridden ? (
            <Badge tone="brand">سفارشی</Badge>
          ) : (
            <Badge tone="neutral">پیش‌فرض سایت</Badge>
          )}
          {item.overridden && (
            <Button variant="ghost" size="xs" onClick={reset} loading={update.isPending}>
              <RotateCcw className="h-3.5 w-3.5" />
              بازگشت به پیش‌فرض
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Field label="فارسی" hint={item.default_fa ? `پیش‌فرض: ${item.default_fa}` : undefined}>
          <Control
            dir="rtl"
            value={fa}
            placeholder={item.default_fa}
            onChange={(e: { target: { value: string } }) => setFa(e.target.value)}
          />
        </Field>
        <Field label="English" hint={item.default_en ? `Default: ${item.default_en}` : undefined}>
          <Control
            dir="ltr"
            value={en}
            placeholder={item.default_en}
            onChange={(e: { target: { value: string } }) => setEn(e.target.value)}
          />
        </Field>
      </div>

      <div className="mt-3 flex justify-end">
        <Button size="sm" onClick={() => save()} loading={update.isPending} disabled={!dirty}>
          <Save className="h-4 w-4" />
          ذخیره
        </Button>
      </div>
    </div>
  );
}
