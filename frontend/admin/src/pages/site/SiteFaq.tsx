import { ArrowDown, ArrowUp, HelpCircle, Plus, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Drawer } from "@/components/ui/Drawer";
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
import { apiErrorMessage } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { FAQ_CATEGORIES, type SiteFaqInput, type SiteFaqItem } from "@/types/api";

const LOCALES = [
  { value: "fa", label: "فارسی" },
  { value: "en", label: "English" },
];

// Mirrors the tab labels the public site renders for each category id.
const CATEGORY_LABEL: Record<string, string> = {
  start: "شروع",
  vol: "حجم و دعوت",
  apps: "اپ‌ها",
  trouble: "عیب‌یابی",
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
        onError: (err) => toast.error(apiErrorMessage(err, "ترتیب ذخیره نشد.")),
      },
    );
  }

  async function remove(item: SiteFaqItem) {
    const ok = await confirm({
      title: "حذف سوال",
      message: `«${item.question}» حذف شود؟ این عمل قابل بازگشت نیست.`,
      tone: "danger",
      confirmLabel: "حذف",
    });
    if (!ok) return;
    del.mutate(item.id, {
      onSuccess: () => toast.success("سوال حذف شد."),
      onError: (err) => toast.error(apiErrorMessage(err, "حذف نشد.")),
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="سوالات متداول"
        sub="سوال‌های صفحهٔ «سوالات متداول» سایت. تغییرات بدون دیپلوی اعمال می‌شوند."
        actions={
          <div className="flex items-center gap-2">
            <Segmented
              value={locale}
              onChange={setLocale}
              options={LOCALES}
              size="sm"
              ariaLabel="زبان"
            />
            <Button size="sm" onClick={() => setEditing("new")}>
              <Plus className="h-4 w-4" />
              سوال تازه
            </Button>
          </div>
        }
      >
        <SiteTabs />
      </PageHeader>

      <div className="flex flex-wrap items-center gap-3">
        <div className="max-w-md flex-1">
          <Input
            aria-label="جستجو در سوال‌ها"
            icon={<Search className="h-4 w-4" />}
            placeholder="جستجو در سوال یا پاسخ…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        {unpublished > 0 && (
          <Badge tone="warning">{formatNumber(unpublished)} مورد منتشرنشده</Badge>
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
            title={filter ? "سوالی با این جستجو پیدا نشد" : "هنوز سوالی ثبت نشده"}
            message={
              filter
                ? undefined
                : "تا وقتی سوالی اینجا نباشد، سایت همان فهرست پیش‌فرض داخل کد را نشان می‌دهد."
            }
            action={
              !filter ? <Button onClick={() => setEditing("new")}>سوال تازه</Button> : undefined
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
                      aria-label="انتقال به بالا"
                      disabled={Boolean(filter) || index === 0 || reorder.isPending}
                      onClick={() => move(index, -1)}
                    >
                      <ArrowUp className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      iconOnly
                      aria-label="انتقال به پایین"
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
                      {!item.published && <Badge tone="warning">منتشرنشده</Badge>}
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm text-content-muted">{item.answer}</p>
                  </button>

                  <Button
                    variant="ghost"
                    size="sm"
                    iconOnly
                    aria-label="حذف"
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
      toast.error("سوال و پاسخ نمی‌توانند خالی باشند.");
      return;
    }
    const opts = {
      onSuccess: () => {
        toast.success(item ? "ذخیره شد." : "سوال اضافه شد.");
        onClose();
      },
      // Surface the server's own reason — a duplicate question (409) and an unknown category (422)
      // must not collapse into one generic "نشد".
      onError: (err: unknown) => toast.error(apiErrorMessage(err, "ذخیره نشد.")),
    };
    if (item) update.mutate({ id: item.id, body }, opts);
    else create.mutate(body, opts);
  }

  return (
    <Drawer
      open
      onClose={onClose}
      title={item ? "ویرایش سوال" : "سوال تازه"}
      sub={item ? `شناسه ${item.id}` : "به انتهای فهرست همان زبان اضافه می‌شود"}
      footer={
        <div className="flex gap-2">
          <Button onClick={save} loading={saving}>
            ذخیره
          </Button>
          <Button variant="ghost" onClick={onClose}>
            انصراف
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <Field label="زبان">
          <Select
            value={form.locale}
            onChange={(e) => setForm({ ...form, locale: e.target.value })}
          >
            {LOCALES.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="دسته" hint="تب‌های صفحهٔ سوالات سایت از همین فهرست ساخته می‌شوند.">
          <Select
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
          >
            {FAQ_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABEL[c] ?? c}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="سوال">
          <Input
            value={form.question}
            maxLength={300}
            onChange={(e) => setForm({ ...form, question: e.target.value })}
          />
        </Field>

        <Field label="پاسخ" hint="متن ساده — سایت آن را بدون HTML نمایش می‌دهد.">
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
          label="منتشر شده"
          hint="خاموش‌کردن، سوال را از سایت برمی‌دارد بدون اینکه حذفش کند."
        />
      </div>
    </Drawer>
  );
}
