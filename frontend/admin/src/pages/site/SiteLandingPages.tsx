import { isAxiosError } from "axios";
import { clsx } from "clsx";
import { FileText, Plus, Save, Trash2 } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import {
  useCreateLanding,
  useDeleteLanding,
  useSiteLandingPages,
  useUpdateLanding,
} from "@/hooks/useSite";
import type { SiteLandingInput, SiteLandingPage } from "@/types/api";

const INPUT =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand dark:border-slate-700 dark:bg-slate-900";

const BLANK: SiteLandingInput = {
  slug: "",
  locale: "fa",
  title: "",
  meta_description: "",
  heading: null,
  body: "",
  location_remark: null,
  published: true,
};

function saveError(e: unknown): string {
  if (isAxiosError(e)) {
    if (e.response?.status === 409) return "این نشانی (slug) در این زبان قبلاً وجود دارد.";
    if (e.response?.status === 422) return "ورودی نامعتبر است (زبان باید fa یا en باشد).";
  }
  return "ذخیره نشد.";
}

export function SiteLandingPages() {
  const { data: pages = [], isLoading } = useSiteLandingPages();
  const [selected, setSelected] = useState<number | "new" | null>(null);

  const active = selected === "new" ? null : (pages.find((p) => p.id === selected) ?? null);
  const editing = selected === "new" || active !== null;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">وب‌سایت</h1>
      <SiteTabs />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <Button
            variant="ghost"
            className="mb-3 w-full justify-start"
            onClick={() => setSelected("new")}
          >
            <Plus className="h-4 w-4" /> صفحه‌ی جدید
          </Button>
          {isLoading ? (
            <div className="flex justify-center py-10">
              <Spinner className="h-6 w-6 text-brand" />
            </div>
          ) : pages.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-400">هنوز صفحه‌ای ساخته نشده.</p>
          ) : (
            <ul className="max-h-[60vh] space-y-1 overflow-y-auto">
              {pages.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => setSelected(p.id)}
                    className={clsx(
                      "flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-sm transition",
                      p.id === selected
                        ? "bg-brand/10 text-brand"
                        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
                    )}
                  >
                    <span dir="ltr" className="truncate">
                      {p.slug}
                    </span>
                    <span className="flex shrink-0 items-center gap-1.5">
                      <span className="text-xs uppercase text-slate-400">{p.locale}</span>
                      {!p.published && <span className="text-xs text-amber-500">پیش‌نویس</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <div className="lg:col-span-2">
          {editing ? (
            <LandingEditor
              key={selected}
              page={active}
              onCreated={(id) => setSelected(id)}
              onDeleted={() => setSelected(null)}
            />
          ) : (
            <Card className="flex h-64 items-center justify-center text-slate-400">
              <div className="text-center">
                <FileText className="mx-auto mb-2 h-8 w-8" />
                یک صفحه را برای ویرایش انتخاب کنید یا صفحه‌ی جدید بسازید
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function LandingEditor({
  page,
  onCreated,
  onDeleted,
}: {
  page: SiteLandingPage | null;
  onCreated: (id: number) => void;
  onDeleted: () => void;
}) {
  const create = useCreateLanding();
  const update = useUpdateLanding();
  const del = useDeleteLanding();
  const [form, setForm] = useState<SiteLandingInput>(
    page
      ? {
          slug: page.slug,
          locale: page.locale,
          title: page.title,
          meta_description: page.meta_description,
          heading: page.heading,
          body: page.body,
          location_remark: page.location_remark,
          published: page.published,
        }
      : BLANK,
  );

  const set = <K extends keyof SiteLandingInput>(key: K, value: SiteLandingInput[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  function submit(e: FormEvent) {
    e.preventDefault();
    if (page) {
      update.mutate(
        { id: page.id, body: form },
        { onSuccess: () => toast.success("ذخیره شد."), onError: (err) => toast.error(saveError(err)) },
      );
    } else {
      create.mutate(form, {
        onSuccess: (created) => {
          toast.success("صفحه ساخته شد.");
          onCreated(created.id);
        },
        onError: (err) => toast.error(saveError(err)),
      });
    }
  }

  function remove() {
    if (!page || !window.confirm("این صفحه حذف شود؟")) return;
    del.mutate(page.id, {
      onSuccess: () => {
        toast.success("حذف شد.");
        onDeleted();
      },
      onError: () => toast.error("حذف نشد."),
    });
  }

  return (
    <Card>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="نشانی (slug)">
            <input
              dir="ltr"
              className={INPUT}
              value={form.slug}
              onChange={(e) => set("slug", e.target.value)}
              placeholder="free-v2ray-config"
            />
          </Field>
          <Field label="زبان">
            <select className={INPUT} value={form.locale} onChange={(e) => set("locale", e.target.value)}>
              <option value="fa">فارسی</option>
              <option value="en">English</option>
            </select>
          </Field>
        </div>
        <Field label="عنوان (title / SEO)">
          <input
            className={INPUT}
            value={form.title}
            onChange={(e) => set("title", e.target.value)}
          />
        </Field>
        <Field label="توضیح متا (meta description)">
          <input
            className={INPUT}
            value={form.meta_description}
            onChange={(e) => set("meta_description", e.target.value)}
          />
        </Field>
        <Field label="سرتیتر صفحه (اختیاری)">
          <input
            className={INPUT}
            value={form.heading ?? ""}
            onChange={(e) => set("heading", e.target.value || null)}
          />
        </Field>
        <Field label="محتوا (body)">
          <textarea
            dir="auto"
            className={clsx(INPUT, "min-h-[160px]")}
            value={form.body}
            onChange={(e) => set("body", e.target.value)}
          />
        </Field>
        <Field label="لوکیشن پیش‌انتخاب در ویجت (نام remark، اختیاری)">
          <input
            className={INPUT}
            value={form.location_remark ?? ""}
            onChange={(e) => set("location_remark", e.target.value || null)}
            placeholder="مثال: آلمان"
          />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.published}
            onChange={(e) => set("published", e.target.checked)}
            className="h-4 w-4 accent-brand"
          />
          منتشرشده (در سایت نمایش داده شود)
        </label>
        <div className="flex justify-between">
          {page ? (
            <Button type="button" variant="danger" onClick={remove} loading={del.isPending}>
              <Trash2 className="h-4 w-4" /> حذف
            </Button>
          ) : (
            <span />
          )}
          <Button type="submit" loading={create.isPending || update.isPending}>
            <Save className="h-4 w-4" /> ذخیره
          </Button>
        </div>
      </form>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-sm">{label}</label>
      {children}
    </div>
  );
}
