import { isAxiosError } from "axios";
import { clsx } from "clsx";
import { Copy, ExternalLink, Eye, FileText, Plus, Save, Trash2 } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Badge } from "@/components/ui/Badge";
import { Button, ExternalLinkButton } from "@/components/ui/Button";
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
  useSiteDerivableLocations,
  useSiteLandingPages,
  useSiteSettings,
  useUpdateLanding,
} from "@/hooks/useSite";
import { useI18n, type MessageKey } from "@/i18n";
import { apiErrorMessage } from "@/lib/api";
import { formatNumber, langLabel } from "@/lib/format";
import { normalizeRemark, resolveSelection } from "@/lib/locations";
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

// The site serves landings at /l/{slug} on the SAME origin the panel is mounted under (/admin/),
// which is what the installer sets up. A relative link therefore always points at the real page.
const siteUrl = (slug: string) => `/l/${slug}`;

// Mirrors the backend rule (^[a-z0-9]+(-[a-z0-9]+)*$) so a bad slug is caught while typing rather
// than on save. The server remains the authority.
const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function saveError(e: unknown, t: (k: MessageKey) => string): string {
  // 409 gets a friendlier phrasing than the server's; everything else (including the slug rule the
  // backend now enforces) shows the server's own explanation rather than a generic failure.
  if (isAxiosError(e) && e.response?.status === 409) {
    return t("sl.slugTaken");
  }
  return apiErrorMessage(e, t("sl.saveFailed"));
}

export function SiteLandingPages() {
  const { t } = useI18n();
  const FILTERS = [
    { value: "", label: t("sl.filter.all") },
    { value: "published", label: t("sl.filter.published") },
    { value: "draft", label: t("sl.filter.draft") },
  ];
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
        title={t("sl.title")}
        sub={t("sl.sub", {
          n: formatNumber(published),
          total: formatNumber(pages.length),
        })}
        actions={
          <Button onClick={() => setSelected("new")}>
            <Plus className="h-4 w-4" /> {t("sl.new")}
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
            ariaLabel={t("sl.filterAria")}
            className="mb-3"
          />
          {isError && pages.length === 0 ? (
            <ErrorState compact onRetry={() => refetch()} />
          ) : isLoading ? (
            <div className="flex justify-center py-10">
              <Spinner className="h-6 w-6 text-brand" />
            </div>
          ) : visible.length === 0 ? (
            <EmptyState icon={FileText} title={t("sl.empty")} />
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
                      {!p.published && <Badge tone="warning">{t("sl.filter.draft")}</Badge>}
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
              <EmptyState icon={FileText} title={t("sl.pick")} message={t("sl.pick.msg")} />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

/** Length/presence checks Google actually cares about, shown while writing rather than never. */
function SeoChecklist({ form }: { form: SiteLandingInput }) {
  const { t } = useI18n();
  const words = htmlToText(form.body).split(" ").filter(Boolean).length;
  const checks = [
    {
      ok: form.title.length >= 20 && form.title.length <= 60,
      label: t("sl.seo.titleLen", { n: formatNumber(form.title.length) }),
      hint: t("sl.seo.titleHint"),
    },
    {
      ok: form.meta_description.length >= 70 && form.meta_description.length <= 160,
      label: t("sl.seo.metaLen", { n: formatNumber(form.meta_description.length) }),
      hint: t("sl.seo.metaHint"),
    },
    {
      ok: Boolean(form.heading?.trim()),
      label: t("sl.seo.h1"),
      hint: t("sl.seo.h1Hint"),
    },
    {
      ok: words >= 150,
      label: t("sl.seo.words", { n: formatNumber(words) }),
      hint: t("sl.seo.wordsHint"),
    },
    {
      ok: SLUG_RE.test(form.slug),
      label: t("sl.seo.slug"),
      hint: t("sl.seo.slugHint"),
    },
  ];
  return (
    <div className="rounded-xl border border-line bg-surface-raised p-3">
      <div className="mb-2 text-xs font-semibold text-content-muted">{t("sl.seo")}</div>
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
  const { t } = useI18n();
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
          onSuccess: () => toast.success(t("sl.saved")),
          onError: (err) => toast.error(saveError(err, t)),
        },
      );
    } else {
      create.mutate(form, {
        onSuccess: (created) => {
          toast.success(t("sl.created"));
          onCreated(created.id);
        },
        onError: (err) => toast.error(saveError(err, t)),
      });
    }
  }

  /** Copy this page into the other locale so a translation starts from the real content. */
  function duplicate() {
    create.mutate(
      { ...form, locale: otherLocale },
      {
        onSuccess: (created) => {
          toast.success(t("sl.copied", { lang: langLabel(otherLocale) }));
          onCreated(created.id);
        },
        onError: (err) => toast.error(saveError(err, t)),
      },
    );
  }

  async function remove() {
    if (!page) return;
    const ok = await confirm({
      title: t("sl.delete.title"),
      message: t("sl.delete.confirm"),
      tone: "danger",
      confirmLabel: t("sl.delete"),
    });
    if (!ok) return;
    del.mutate(page.id, {
      onSuccess: () => {
        toast.success(t("sl.deleted"));
        onDeleted();
      },
      onError: (err) => toast.error(apiErrorMessage(err, t("sl.deleteFailed"))),
    });
  }

  return (
    <Card>
      <CardHeader
        title={page ? t("sl.edit.title") : t("sl.new")}
        // Its own LTR run: in the RTL header «/l/free-v2ray-config» laid out as
        // «l/free-v2ray-config/», the slashes moving to the far end.
        sub={
          form.slug ? (
            <span dir="ltr" className="font-mono">
              /l/{form.slug}
            </span>
          ) : undefined
        }
        icon={FileText}
        action={
          <div className="flex items-center gap-1">
            {page?.published && (
              <ExternalLinkButton href={siteUrl(page.slug)} variant="ghost" size="sm">
                <ExternalLink className="h-4 w-4" />
                {t("sl.viewOnSite")}
              </ExternalLinkButton>
            )}
            {page && !twinExists && (
              <Button variant="ghost" size="sm" onClick={duplicate} loading={create.isPending}>
                <Copy className="h-4 w-4" />
                {t("sl.copyTo", { lang: langLabel(otherLocale) })}
              </Button>
            )}
          </div>
        }
      />
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label={t("sl.field.slug")}
            error={slugInvalid ? t("sl.field.slugError") : undefined}
          >
            <Input
              dir="ltr"
              value={form.slug}
              onChange={(e) => set("slug", e.target.value)}
              placeholder="free-v2ray-config"
            />
          </Field>
          <Field label={t("sl.field.locale")}>
            <Select value={form.locale} onChange={(e) => set("locale", e.target.value)}>
              <option value="fa">{langLabel("fa")}</option>
              <option value="en">{langLabel("en")}</option>
            </Select>
          </Field>
        </div>
        <Field label={t("sl.field.title")}>
          <Input value={form.title} onChange={(e) => set("title", e.target.value)} />
        </Field>
        <Field label={t("sl.field.meta")}>
          <Input
            value={form.meta_description}
            onChange={(e) => set("meta_description", e.target.value)}
          />
        </Field>
        <Field label={t("sl.field.heading")}>
          <Input
            value={form.heading ?? ""}
            onChange={(e) => set("heading", e.target.value || null)}
          />
        </Field>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label className="text-sm font-medium text-content">{t("sl.field.body")}</label>
            <Button
              type="button"
              variant="ghost"
              size="xs"
              onClick={() => setPreview((v) => !v)}
              aria-pressed={preview}
            >
              <Eye className="h-3.5 w-3.5" />
              {preview ? t("sl.field.edit") : t("sl.field.preview")}
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

        <LandingLocationField
          value={form.location_remark}
          onChange={(v) => set("location_remark", v)}
        />

        <Switch
          checked={form.published}
          onChange={(v) => set("published", v)}
          label={t("sl.field.published")}
          hint={t("sl.field.publishedHint")}
        />

        <SeoChecklist form={form} />

        <div className="flex justify-between">
          {page ? (
            <Button type="button" variant="danger" onClick={remove} loading={del.isPending}>
              <Trash2 className="h-4 w-4" /> {t("sl.delete")}
            </Button>
          ) : (
            <span />
          )}
          <Button
            type="submit"
            loading={create.isPending || update.isPending}
            disabled={!form.slug.trim() || !form.title.trim() || slugInvalid}
          >
            <Save className="h-4 w-4" /> {t("sl.save")}
          </Button>
        </div>
      </form>
    </Card>
  );
}

/**
 * The landing's pre-selected location, picked from what the site's picker OFFERS.
 *
 * It was free text: a typo — or a name the squad has since stopped serving — saved without a word,
 * and the widget on that landing then preselected nothing. The offered list is what the public
 * picker offers: the site's stored subset matched against the squad's live names, or every live
 * name when that is empty or matches none of them (`[]` means "all"). A stored value no
 * longer on it stays visible and marked, so opening an old page never silently changes it. With
 * nothing to offer (no squad yet, or the panel down) it falls back to a text box; the server makes
 * the same best-effort check on save.
 */
function LandingLocationField({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (v: string | null) => void;
}) {
  const { t } = useI18n();
  const { data: settings } = useSiteSettings();
  const squad = settings?.trial_squad ?? "";
  const stored = settings?.locations ?? [];
  const live = useSiteDerivableLocations(squad);
  // Matched against the LIVE names, as the public picker does: the stored list alone kept offering
  // names the squad had dropped, which the site never shows — so the widget preselected nothing.
  const selection = live.data ? resolveSelection(stored, live.data) : null;
  const offered = !live.data ? stored : selection?.all ? live.data : (selection?.save ?? []);
  // By NORMALISED name, as the server checks it — a spelling difference is not a stale value.
  const stale =
    Boolean(value) && !offered.some((o) => normalizeRemark(o) === normalizeRemark(value!));

  if (offered.length === 0) {
    return (
      <Field label={t("sl.field.location")} hint={t("sl.field.locationHint")}>
        <Input
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value || null)}
          placeholder={t("loc.placeholder")}
        />
      </Field>
    );
  }
  return (
    <Field
      label={t("sl.field.location")}
      hint={stale ? t("sl.field.locationStale") : t("sl.field.locationPick")}
    >
      <Select value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}>
        <option value="">{t("ss.popular.none")}</option>
        {stale && <option value={value!}>{t("ss.popular.staleOption", { name: value! })}</option>}
        {offered.map((l) => (
          <option key={l} value={l}>
            {l}
          </option>
        ))}
      </Select>
    </Field>
  );
}
