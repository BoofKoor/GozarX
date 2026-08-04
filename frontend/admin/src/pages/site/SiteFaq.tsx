import { ArrowDown, ArrowUp, HelpCircle, Plus, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { RecordDialog } from "@/components/ui/RecordDialog";
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
  useCreateFaq,
  useDeleteFaq,
  useReorderFaq,
  useSiteFaq,
  useUpdateFaq,
} from "@/hooks/useSite";
import { useI18n, type MessageKey } from "@/i18n";
import { apiErrorMessage } from "@/lib/api";
import { formatNumber, langLabel } from "@/lib/format";
import { FAQ_CATEGORIES, type SiteFaqInput, type SiteFaqItem } from "@/types/api";

const LOCALES = ["fa", "en"];

// Mirrors the tab labels the public site renders for each category id.
const CATEGORY_LABEL: Record<string, MessageKey> = {
  start: "sf.cat.start",
  vol: "sf.cat.vol",
  apps: "sf.cat.apps",
  trouble: "sf.cat.trouble",
};

const BLANK = (locale: string): SiteFaqInput => ({
  locale,
  category: "start",
  question: "",
  answer: "",
  published: true,
});

/**
 * The public site's FAQ, editable.
 *
 * These 16 questions used to be compiled into the site's bundle: answering a new recurring support
 * question meant a code change and a redeploy. The order is the operator's — items are stored with
 * an explicit position and moved with one atomic reorder call, so the list on the site matches the
 * list here exactly.
 */
export function SiteFaq() {
  const { t } = useI18n();
  const [locale, setLocale] = useState("fa");
  const [filter, setFilter] = useState("");
  const [editing, setEditing] = useState<SiteFaqItem | "new" | null>(null);

  const { data, isLoading, isError, refetch } = useSiteFaq(locale);
  const reorder = useReorderFaq();
  const del = useDeleteFaq();
  const confirm = useConfirm();

  const items = data ?? [];
  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) return items;
    return items.filter(
      (i) => i.question.toLowerCase().includes(needle) || i.answer.toLowerCase().includes(needle),
    );
  }, [items, filter]);

  const unpublished = items.filter((i) => !i.published).length;

  /** Swap an item with its neighbour and send the WHOLE resulting order. */
  function move(index: number, delta: number) {
    const next = [...items];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    reorder.mutate(
      next.map((i) => i.id),
      {
        onError: (err) => toast.error(apiErrorMessage(err, t("sf.reorderFailed"))),
      },
    );
  }

  async function remove(item: SiteFaqItem) {
    const ok = await confirm({
      title: t("sf.delete.title"),
      message: t("sf.delete.confirm", { q: item.question }),
      tone: "danger",
      confirmLabel: t("sf.delete"),
    });
    if (!ok) return;
    del.mutate(item.id, {
      onSuccess: () => toast.success(t("sf.deleted")),
      onError: (err) => toast.error(apiErrorMessage(err, t("sf.deleteFailed"))),
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("sf.title")}
        sub={t("sf.sub")}
        actions={
          <div className="flex items-center gap-2">
            <Segmented
              value={locale}
              onChange={setLocale}
              options={LOCALES.map((l) => ({ value: l, label: langLabel(l) }))}
              size="sm"
              ariaLabel={t("sf.localeAria")}
            />
            <Button size="sm" onClick={() => setEditing("new")}>
              <Plus className="h-4 w-4" />
              {t("sf.new")}
            </Button>
          </div>
        }
      >
        <SiteTabs />
      </PageHeader>

      <div className="flex flex-wrap items-center gap-3">
        <div className="max-w-md flex-1">
          <Input
            aria-label={t("sf.searchAria")}
            icon={<Search className="h-4 w-4" />}
            placeholder={t("sf.search")}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        {unpublished > 0 && (
          <Badge tone="warning">{t("sf.unpublishedCount", { n: formatNumber(unpublished) })}</Badge>
        )}
      </div>

      {isError && !data ? (
        <ErrorState onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="flex justify-center py-20">
          <Spinner className="h-8 w-8 text-brand" />
        </div>
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState
            icon={HelpCircle}
            title={filter ? t("sf.empty.filtered") : t("sf.empty.none")}
            message={filter ? undefined : t("sf.empty.noneMsg")}
            action={
              !filter ? <Button onClick={() => setEditing("new")}>{t("sf.new")}</Button> : undefined
            }
          />
        </Card>
      ) : (
        <ul className="space-y-3">
          {visible.map((item) => {
            const index = items.indexOf(item);
            return (
              <li key={item.id}>
                <Card className="flex items-start gap-3">
                  {/* Reordering is disabled while a search is filtering the list: the arrows move an
                      item relative to its NEIGHBOURS, and the neighbours on screen aren't the real
                      ones when rows are hidden. */}
                  <div className="flex flex-col gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      iconOnly
                      aria-label={t("sf.moveUp")}
                      disabled={Boolean(filter) || index === 0 || reorder.isPending}
                      onClick={() => move(index, -1)}
                    >
                      <ArrowUp className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      iconOnly
                      aria-label={t("sf.moveDown")}
                      disabled={Boolean(filter) || index === items.length - 1 || reorder.isPending}
                      onClick={() => move(index, 1)}
                    >
                      <ArrowDown className="h-4 w-4" />
                    </Button>
                  </div>

                  <button
                    type="button"
                    onClick={() => setEditing(item)}
                    className="min-w-0 flex-1 text-start"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-content">{item.question}</span>
                      <Badge tone="neutral">{CATEGORY_LABEL[item.category] ?? item.category}</Badge>
                      {!item.published && <Badge tone="warning">{t("sf.unpublished")}</Badge>}
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm text-content-muted">{item.answer}</p>
                  </button>

                  <Button
                    variant="ghost"
                    size="sm"
                    iconOnly
                    aria-label={t("sf.delete")}
                    onClick={() => remove(item)}
                  >
                    <Trash2 className="h-4 w-4 text-danger-600" />
                  </Button>
                </Card>
              </li>
            );
          })}
        </ul>
      )}

      {editing != null && (
        <FaqEditor
          item={editing === "new" ? null : editing}
          locale={locale}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function FaqEditor({
  item,
  locale,
  onClose,
}: {
  item: SiteFaqItem | null;
  locale: string;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const [form, setForm] = useState<SiteFaqInput>(
    item
      ? {
          locale: item.locale,
          category: item.category,
          question: item.question,
          answer: item.answer,
          published: item.published,
          position: item.position,
        }
      : BLANK(locale),
  );
  const create = useCreateFaq();
  const update = useUpdateFaq();
  const saving = create.isPending || update.isPending;

  function save() {
    const body: SiteFaqInput = {
      ...form,
      question: form.question.trim(),
      answer: form.answer.trim(),
    };
    if (!body.question || !body.answer) {
      toast.error(t("sf.emptyFields"));
      return;
    }
    const opts = {
      onSuccess: () => {
        toast.success(item ? t("sf.saved") : t("sf.added"));
        onClose();
      },
      // Surface the server's own reason — a duplicate question (409) and an unknown category (422)
      // must not collapse into one generic failure.
      onError: (err: unknown) => toast.error(apiErrorMessage(err, t("sf.saveFailed"))),
    };
    if (item) update.mutate({ id: item.id, body }, opts);
    else create.mutate(body, opts);
  }

  return (
    <RecordDialog
      open
      onClose={onClose}
      title={item ? t("sf.edit.title") : t("sf.new")}
      sub={item ? t("sf.edit.id", { id: formatNumber(item.id) }) : t("sf.edit.newSub")}
      footer={
        <div className="flex gap-2">
          <Button onClick={save} loading={saving}>
            {t("sf.save")}
          </Button>
          <Button variant="ghost" onClick={onClose}>
            {t("sf.cancel")}
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <Field label={t("sf.field.locale")}>
          <Select
            value={form.locale}
            onChange={(e) => setForm({ ...form, locale: e.target.value })}
          >
            {LOCALES.map((l) => (
              <option key={l} value={l}>
                {langLabel(l)}
              </option>
            ))}
          </Select>
        </Field>

        <Field label={t("sf.field.category")} hint={t("sf.field.categoryHint")}>
          <Select
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
          >
            {FAQ_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABEL[c] ? t(CATEGORY_LABEL[c]) : c}
              </option>
            ))}
          </Select>
        </Field>

        <Field label={t("sf.field.question")}>
          <Input
            value={form.question}
            maxLength={300}
            onChange={(e) => setForm({ ...form, question: e.target.value })}
          />
        </Field>

        <Field label={t("sf.field.answer")} hint={t("sf.field.answerHint")}>
          <Textarea
            rows={6}
            value={form.answer}
            maxLength={4000}
            onChange={(e) => setForm({ ...form, answer: e.target.value })}
          />
        </Field>

        <Switch
          checked={form.published}
          onChange={(published) => setForm({ ...form, published })}
          label={t("sf.field.published")}
          hint={t("sf.field.publishedHint")}
        />
      </div>
    </RecordDialog>
  );
}
