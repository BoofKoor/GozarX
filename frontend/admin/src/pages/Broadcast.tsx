import { clsx } from "clsx";
import { Eye, Send, Users as UsersIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useAudience, useSendBroadcast } from "@/hooks/useBroadcast";
import { langLabel } from "@/lib/format";
import type { Lang } from "@/types/api";

const ALL_LANGS: Lang[] = ["fa", "en", "ru"];

export function Broadcast() {
  const [text, setText] = useState("");
  const [langs, setLangs] = useState<Lang[]>(ALL_LANGS); // all groups selected by default
  const { data: audience } = useAudience(langs);
  const send = useSendBroadcast();

  // No language selected ⇒ nobody (send is blocked); the backend would read "" as everyone, so we
  // never reach it — we show 0 and disable the button instead.
  const recipients = langs.length ? audience?.recipients : 0;
  const allSelected = langs.length === ALL_LANGS.length;
  const summary = allSelected ? "همهٔ زبان‌ها" : langs.map(langLabel).join("، ");

  function toggle(code: Lang) {
    setLangs((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  }

  function submit() {
    const body = text.trim();
    if (!body || langs.length === 0) return;
    if (!window.confirm(`ارسال این پیام به ${recipients ?? "؟"} کاربر (${summary})؟`)) return;
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
      <h1 className="text-xl font-bold">پیام همگانی</h1>

      <Card className="max-w-2xl space-y-4">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <UsersIcon className="h-4 w-4" />
          گیرندگان: <span className="font-bold text-brand">{recipients ?? "…"}</span> کاربر
        </div>

        <div>
          <div className="mb-1.5 text-xs text-slate-500 dark:text-slate-400">
            زبان گیرندگان (پیش‌فرض: همه):
          </div>
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
                      : "border-slate-300 text-slate-500 hover:border-brand dark:border-slate-700",
                  )}
                >
                  {langLabel(code)}
                </button>
              );
            })}
          </div>
          {langs.length === 0 && (
            <p className="mt-1.5 text-xs text-rose-500">حداقل یک زبان را انتخاب کنید.</p>
          )}
        </div>

        <p className="text-xs text-slate-500 dark:text-slate-400">
          متن به کاربرانِ زبان‌های انتخاب‌شده ارسال می‌شود. قالب‌بندی HTML تلگرام مجاز است (
          <code dir="ltr">{"<b> <i> <a> <code>"}</code>). ارسال در پس‌زمینه انجام می‌شود و پیشرفت آن
          در تلگرامِ مالک گزارش داده می‌شود.
        </p>

        <textarea
          className="min-h-[160px] w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand dark:border-slate-700 dark:bg-slate-900"
          placeholder="متن پیام…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          dir="auto"
        />

        {text.trim() && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-xs text-slate-500">
              <Eye className="h-3.5 w-3.5" />
              پیش‌نمایش:
            </div>
            <div
              className="whitespace-pre-wrap rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 text-sm dark:border-slate-700 dark:bg-slate-800"
              dir="auto"
              dangerouslySetInnerHTML={{ __html: text }}
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
