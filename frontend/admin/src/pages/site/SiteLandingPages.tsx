import { isAxiosError } from "axios";
import { clsx } from "clsx";
import { Copy, ExternalLink, Eye, FileText, Plus, Save, Trash2 } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";
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
import { Segmented } from "@/components/ui/Segmented";
import { Select } from "@/components/ui/Select";
import { Spinner } from "@/components/ui/Spinner";
import { Switch } from "@/components/ui/Switch";
import { Textarea } from "@/components/ui/Textarea";
import { useConfirm } from "@/components/ui/confirm";
import {
  useCreateLanding,
  useDeleteLanding,
  useSiteLandingPages,
  useUpdateLanding,
} from "@/hooks/useSite";
import { apiErrorMessage } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { htmlToText, sanitizeArticleHtml } from "@/lib/sanitize";
import type { SiteLandingInput, SiteLandingPage } from "@/types/api";

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

const FILTERS = [
  { value: "", label: "همه" },
  { value: "published", label: "منتشرشده" },
  { value: "draft", label: "پیش‌نویس" },
];

// The site serves landings at /l/{slug} on the SAME origin the panel is mounted under (/admin/),
// which is what the installer sets up. A relative link therefore always points at the real page.
const siteUrl = (slug: string) => `/l/${slug}`;

// Mirrors the backend rule (^[a-z0-9]+(-[a-z0-9]+)*$) so a bad slug is caught while typing rather
// than on save. The server remains the authority.
const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function saveError(e: unknown): string {
  // 409 gets a friendlier phrasing than the server's; everything else (including the slug rule the
  // backend now enforces) shows the server's own explanation rather than a generic failure.
  if (isAxiosError(e) && e.response?.status === 409) {
    return "این نشانی (slug) در این زبان قبلاً وجود دارد.";
  }
  return apiErrorMessage(e, "ذخیره نشد.");
}

export function SiteLandingPages() {
  const { data: pages = [], isLoading, isError, refetch } = useSiteLandingPages();
  const [selected, setSelected] = useState<number | "new" | null>(null);
  const [filter, setFilter] = useState("");

  const visible = useMemo(() => {
    const rows = pages.filter(
      (p) =>
        !filter || (filter === "published" && p.published) || (filter === "draft" && !p.published),
    );
    // Most-recently edited first: the page you were just working on is the one you want next.
    return [...rows].sort((a, b) => (b.updated_at ?? "").localeCompare(a.updated_at ?? ""));
  }, [pages, filter]);

  const active = selected === "new" ? null : (pages.find((p) => p.id === selected) ?? null);
  const editing = selected === "new" || active !== null;
  const published = pages.filter((p) => p.published).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="صفحه‌های فرود"
        sub={`${formatNumber(published)} منتشرشده از ${formatNumber(pages.length)} صفحه — در سایت‌مپ و نتایج جستجو دیده می‌شوند.`}
        actions={
          <Button onClick={() => setSelected("new")}>
            <Plus className="h-4 w-4" /> صفحهٔ جدید
          </Button>
        }
      >
        <SiteTabs />
      </PageHeader>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <Segmented
            value={filter}
            onChange={setFilter}
            options={FILTERS}
            size="sm"
            ariaLabel="فیلتر انتشار"
            className="mb-3"
          />
          {isError && pages.length === 0 ? (
            <ErrorState compact onRetry={() => refetch()} />
          ) : isLoading ? (
            <div className="flex justify-center py-10">
              <Spinner className="h-6 w-6 text-brand" />
            </div>
          ) : visible.length === 0 ? (
            <EmptyState icon={FileText} title="صفحه‌ای نیست" />
          ) : (
            <ul className="scrollbar-thin max-h-[60vh] space-y-1 overflow-y-auto">
              {visible.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => setSelected(p.id)}
                    className={clsx(
                      "flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-sm transition",
                      p.id === selected
                        ? "bg-brand/10 text-brand-700"
                        : "text-content-muted hover:bg-surface-hover",
                    )}
                  >
                    <span dir="ltr" className="truncate font-mono text-xs">
                      {p.slug}
                    </span>
                    <span className="flex shrink-0 items-center gap-1.5">
                      <span className="text-xs uppercase text-content-subtle">{p.locale}</span>
                      {!p.published && <Badge tone="warning">پیش‌نویس</Badge>}
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
              siblings={pages}
              onCreated={(id) => setSelected(id)}
              onDeleted={() => setSelected(null)}
            />
          ) : (
            <Card>
              <EmptyState
                icon={FileText}
                title="یک صفحه را برای ویرایش انتخاب کنید"
                message="یا صفحهٔ جدیدی بسازید — هر صفحه یک نشانی /l/… در سایت می‌گیرد."
              />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

/** Length/presence checks Google actually cares about, shown while writing rather than never. */
function SeoChecklist({ form }: { form: SiteLandingInput }) {
  const words = htmlToText(form.body).split(" ").filter(Boolean).length;
  const checks = [
    {
      ok: form.title.length >= 20 && form.title.length <= 60,
      label: `طول عنوان: ${formatNumber(form.title.length)} نویسه`,
      hint: "بین ۲۰ تا ۶۰ نویسه بهترین است.",
    },
    {
      ok: form.meta_description.length >= 70 && form.meta_description.length <= 160,
      label: `طول توضیح متا: ${formatNumber(form.meta_description.length)} نویسه`,
      hint: "بین ۷۰ تا ۱۶۰ نویسه بهترین است.",
    },
    {
      ok: Boolean(form.heading?.trim()),
      label: "سرتیتر صفحه (H1)",
      hint: "بدون سرتیتر، عنوان سئو به‌جای آن استفاده می‌شود.",
    },
    {
      ok: words >= 150,
      label: `حجم محتوا: ${formatNumber(words)} کلمه`,
      hint: "زیر ۱۵۰ کلمه معمولاً «محتوای کم» شمرده می‌شود.",
    },
    {
      ok: SLUG_RE.test(form.slug),
      label: "نشانی (slug) معتبر",
      hint: "فقط حروف کوچک انگلیسی، عدد و خط تیره.",
    },
  ];
  return (
    <div className="rounded-xl border border-line bg-surface-sunken p-3">
      <div className="mb-2 text-xs font-semibold text-content-muted">چک‌لیست سئو</div>
      <ul className="space-y-1.5">
        {checks.map((c) => (
          <li key={c.label} className="flex items-start gap-2 text-xs">
            <span
              className={clsx(
                "mt-0.5 h-2 w-2 shrink-0 rounded-full",
                c.ok ? "bg-success-500" : "bg-warning-500",
              )}
              aria-hidden
            />
            <span className={c.ok ? "text-content-muted" : "text-content"}>
              {c.label}
              {!c.ok && <span className="block text-content-subtle">{c.hint}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LandingEditor({
  page,
  siblings,
  onCreated,
  onDeleted,
}: {
  page: SiteLandingPage | null;
  siblings: SiteLandingPage[];
  onCreated: (id: number) => void;
  onDeleted: () => void;
}) {
  const create = useCreateLanding();
  const update = useUpdateLanding();
  const del = useDeleteLanding();
  const confirm = useConfirm();
  const [preview, setPreview] = useState(false);
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

  const otherLocale = form.locale === "fa" ? "en" : "fa";
  const twinExists = siblings.some((p) => p.slug === form.slug && p.locale === otherLocale);
  const slugInvalid = form.slug.length > 0 && !SLUG_RE.test(form.slug);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (page) {
      update.mutate(
        { id: page.id, body: form },
        {
          onSuccess: () => toast.success("ذخیره شد."),
          onError: (err) => toast.error(saveError(err)),
        },
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

  /** Copy this page into the other locale so a translation starts from the real content. */
  function duplicate() {
    create.mutate(
      { ...form, locale: otherLocale },
      {
        onSuccess: (created) => {
          toast.success(`نسخهٔ ${otherLocale === "fa" ? "فارسی" : "انگلیسی"} ساخته شد.`);
          onCreated(created.id);
        },
        onError: (err) => toast.error(saveError(err)),
      },
    );
  }

  async function remove() {
    if (!page) return;
    const ok = await confirm({
      title: "حذف صفحه",
      message: "این صفحهٔ فرود حذف شود؟ این عمل قابل بازگشت نیست.",
      tone: "danger",
      confirmLabel: "حذف",
    });
    if (!ok) return;
    del.mutate(page.id, {
      onSuccess: () => {
        toast.success("حذف شد.");
        onDeleted();
      },
      onError: (err) => toast.error(apiErrorMessage(err, "حذف نشد.")),
    });
  }

  return (
    <Card>
      <CardHeader
        title={page ? "ویرایش صفحه" : "صفحهٔ جدید"}
        sub={form.slug ? `/l/${form.slug}` : undefined}
        icon={FileText}
        action={
          <div className="flex items-center gap-1">
            {page?.published && (
              <a href={siteUrl(page.slug)} target="_blank" rel="noopener noreferrer">
                <Button variant="ghost" size="sm">
                  <ExternalLink className="h-4 w-4" />
                  مشاهده در سایت
                </Button>
              </a>
            )}
            {page && !twinExists && (
              <Button variant="ghost" size="sm" onClick={duplicate} loading={create.isPending}>
                <Copy className="h-4 w-4" />
                کپی به {otherLocale === "fa" ? "فارسی" : "English"}
              </Button>
            )}
          </div>
        }
      />
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="نشانی (slug)"
            error={slugInvalid ? "فقط حروف کوچک انگلیسی، عدد و خط تیره." : undefined}
          >
            <Input
              dir="ltr"
              value={form.slug}
              onChange={(e) => set("slug", e.target.value)}
              placeholder="free-v2ray-config"
            />
          </Field>
          <Field label="زبان">
            <Select value={form.locale} onChange={(e) => set("locale", e.target.value)}>
              <option value="fa">فارسی</option>
              <option value="en">English</option>
            </Select>
          </Field>
        </div>
        <Field label="عنوان (title / SEO)">
          <Input value={form.title} onChange={(e) => set("title", e.target.value)} />
        </Field>
        <Field label="توضیح متا (meta description)">
          <Input
            value={form.meta_description}
            onChange={(e) => set("meta_description", e.target.value)}
          />
        </Field>
        <Field label="سرتیتر صفحه (اختیاری)">
          <Input
            value={form.heading ?? ""}
            onChange={(e) => set("heading", e.target.value || null)}
          />
        </Field>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label className="text-sm font-medium text-content">محتوا (HTML)</label>
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={() => setPreview((v) => !v)}
              aria-pressed={preview}
            >
              <Eye className="h-3.5 w-3.5" />
              {preview ? "ویرایش" : "پیش‌نمایش"}
            </Button>
          </div>
          {preview ? (
            // Sanitised before injection: the panel holds the admin JWTs, so a pasted
            // `<img onerror=…>` must never execute here even though the body is trusted content.
            <div
              className="min-h-[160px] rounded-xl border border-dashed border-line-strong bg-surface-sunken p-3 text-sm leading-relaxed text-content"
              dir="auto"
              dangerouslySetInnerHTML={{ __html: sanitizeArticleHtml(form.body) }}
            />
          ) : (
            <Textarea
              dir="auto"
              className="min-h-[160px] font-mono text-xs"
              value={form.body}
              onChange={(e) => set("body", e.target.value)}
            />
          )}
        </div>

        <Field
          label="لوکیشن پیش‌انتخاب در ویجت (اختیاری)"
          hint="نام remark — بازدیدکنندهٔ این صفحه همان لوکیشن را از پیش انتخاب‌شده می‌بیند."
        >
          <Input
            value={form.location_remark ?? ""}
            onChange={(e) => set("location_remark", e.target.value || null)}
            placeholder="مثال: آلمان"
          />
        </Field>

        <Switch
          checked={form.published}
          onChange={(v) => set("published", v)}
          label="منتشرشده"
          hint="صفحه‌های پیش‌نویس در سایت و سایت‌مپ دیده نمی‌شوند."
        />

        <SeoChecklist form={form} />

        <div className="flex justify-between">
          {page ? (
            <Button type="button" variant="danger" onClick={remove} loading={del.isPending}>
              <Trash2 className="h-4 w-4" /> حذف
            </Button>
          ) : (
            <span />
          )}
          <Button
            type="submit"
            loading={create.isPending || update.isPending}
            disabled={!form.slug.trim() || !form.title.trim() || slugInvalid}
          >
            <Save className="h-4 w-4" /> ذخیره
          </Button>
        </div>
      </form>
    </Card>
  );
}
