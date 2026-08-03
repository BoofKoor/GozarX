import { clsx } from "clsx";
import { Eye, Send, Users as UsersIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useConfirm } from "@/components/ui/confirm";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAudience, useSendBroadcast } from "@/hooks/useBroadcast";
import { formatNumber, langLabel, telegramPreviewHtml } from "@/lib/format";
import type { Lang } from "@/types/api";

const ALL_LANGS: Lang[] = ["fa", "en", "ru"];

export function Broadcast() {
  const [text, setText] = useState("");
  const [langs, setLangs] = useState<Lang[]>(ALL_LANGS); // all groups selected by default
  const { data: audience, isError: audienceError } = useAudience(langs);
  const send = useSendBroadcast();
  const confirm = useConfirm();

  // No language selected ⇒ nobody (send is blocked); the backend would read "" as everyone, so we
  // never reach it — we show 0 and disable the button instead.
  const recipients = langs.length ? audience?.recipients : 0;
  const allSelected = langs.length === ALL_LANGS.length;
  const summary = allSelected ? "همهٔ زبان‌ها" : langs.map(langLabel).join("، ");

  function toggle(code: Lang) {
    setLangs((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  }

  async function submit() {
    const body = text.trim();
    if (!body || langs.length === 0) return;
    const ok = await confirm({
      title: "ارسال پیام همگانی",
      message: `این پیام به ${formatNumber(recipients ?? 0)} کاربر (${summary}) ارسال شود؟`,
      confirmLabel: "ارسال",
    });
    if (!ok) return;
    send.mutate(
      { text: body, languages: langs },
      {
        onSuccess: (r) => {
          toast.success(`در صف ارسال به ${r.recipients} کاربر (${summary}) قرار گرفت.`);
          setText("");
        },
        onError: () => toast.error("ارسال نشد."),
      },
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="پیام همگانی" />

      <Card className="max-w-2xl space-y-4">
        <div className="flex items-center gap-2 text-sm text-content-muted">
          <UsersIcon className="h-4 w-4" />
          گیرندگان:{" "}
          <span className="font-bold text-brand">
            {recipients ?? (audienceError ? "—" : "…")}
          </span>{" "}
          کاربر
        </div>

        <div>
          <div className="mb-1.5 text-xs text-content-muted">زبان گیرندگان (پیش‌فرض: همه):</div>
          <div className="flex flex-wrap gap-2">
            {ALL_LANGS.map((code) => {
              const on = langs.includes(code);
              return (
                <button
                  key={code}
                  type="button"
                  onClick={() => toggle(code)}
                  aria-pressed={on}
                  className={clsx(
                    "rounded-full border px-3 py-1 text-sm transition-colors",
                    on
                      ? "border-brand bg-brand text-white"
                      : "border-line-strong text-content-muted hover:border-brand",
                  )}
                >
                  {langLabel(code)}
                </button>
              );
            })}
          </div>
          {langs.length === 0 && (
            <p className="mt-1.5 text-xs text-danger-600">حداقل یک زبان را انتخاب کنید.</p>
          )}
        </div>

        <p className="text-xs text-content-muted">
          متن به کاربرانِ زبان‌های انتخاب‌شده ارسال می‌شود. قالب‌بندی HTML تلگرام مجاز است (
          <code dir="ltr">{"<b> <i> <a> <code>"}</code>). ارسال در پس‌زمینه انجام می‌شود و پیشرفت آن
          در تلگرامِ مالک گزارش داده می‌شود.
        </p>

        <textarea
          className="field-control min-h-[160px]"
          placeholder="متن پیام…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          dir="auto"
        />

        {text.trim() && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-xs text-content-muted">
              <Eye className="h-3.5 w-3.5" />
              پیش‌نمایش:
            </div>
            <div
              className="whitespace-pre-wrap rounded-lg border border-dashed border-line-strong bg-surface-sunken p-3 text-sm"
              dir="auto"
              dangerouslySetInnerHTML={{ __html: telegramPreviewHtml(text) }}
            />
          </div>
        )}

        <div className="flex justify-end">
          <Button
            onClick={submit}
            loading={send.isPending}
            disabled={!text.trim() || langs.length === 0}
          >
            <Send className="h-4 w-4" />
            {allSelected ? "ارسال به همه" : `ارسال به ${summary}`}
          </Button>
        </div>
      </Card>
    </div>
  );
}
