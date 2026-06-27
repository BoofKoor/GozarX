import { Eye, Send, Users as UsersIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useAudience, useSendBroadcast } from "@/hooks/useBroadcast";

export function Broadcast() {
  const { data: audience } = useAudience();
  const send = useSendBroadcast();
  const [text, setText] = useState("");

  const recipients = audience?.recipients;

  function submit() {
    const body = text.trim();
    if (!body) return;
    if (!window.confirm(`ارسال این پیام به ${recipients ?? "همهٔ"} کاربر؟`)) return;
    send.mutate(body, {
      onSuccess: (r) => {
        toast.success(`در صف ارسال به ${r.recipients} کاربر قرار گرفت.`);
        setText("");
      },
      onError: () => toast.error("ارسال نشد."),
    });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">پیام همگانی</h1>

      <Card className="max-w-2xl space-y-4">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <UsersIcon className="h-4 w-4" />
          گیرندگان: <span className="font-bold text-brand">{recipients ?? "…"}</span> کاربر
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          متن به همهٔ کاربران ربات ارسال می‌شود. قالب‌بندی HTML تلگرام مجاز است (
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
          <Button onClick={submit} loading={send.isPending} disabled={!text.trim()}>
            <Send className="h-4 w-4" />
            ارسال به همه
          </Button>
        </div>
      </Card>
    </div>
  );
}
