import { Send, Users as UsersIcon } from "lucide-react";
import { type ReactNode, useState } from "react";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useSendSitePush, useSitePushAudience } from "@/hooks/useSite";

const INPUT =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand dark:border-slate-700 dark:bg-slate-900";

export function SitePush() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [url, setUrl] = useState("");
  const { data: audience } = useSitePushAudience();
  const send = useSendSitePush();
  const recipients = audience?.recipients;

  function submit() {
    const t = title.trim();
    const b = body.trim();
    if (!t || !b) return;
    if (!window.confirm(`ارسال این اعلان به ${recipients ?? "؟"} دستگاه؟`)) return;
    send.mutate(
      { title: t, body: b, url: url.trim() },
      {
        onSuccess: (r) => {
          toast.success(`در صف ارسال به ${r.recipients} دستگاه قرار گرفت.`);
          setTitle("");
          setBody("");
          setUrl("");
        },
        onError: () => toast.error("ارسال نشد."),
      },
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">وب‌سایت</h1>
      <SiteTabs />

      <Card className="max-w-2xl space-y-4">
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <UsersIcon className="h-4 w-4" />
          گیرندگان: <span className="font-bold text-brand">{recipients ?? "…"}</span> دستگاهِ مشترک
        </div>
        <Field label="عنوان اعلان">
          <input
            className={INPUT}
            dir="auto"
            maxLength={120}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </Field>
        <Field label="متن اعلان">
          <textarea
            className={`${INPUT} min-h-[120px]`}
            dir="auto"
            maxLength={300}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </Field>
        <Field label="لینک مقصد (اختیاری)">
          <input
            className={INPUT}
            dir="ltr"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="/status"
          />
        </Field>
        <p className="text-xs text-slate-400">
          اعلان در پس‌زمینه (arq worker) به همهٔ دستگاه‌های مشترکِ Web Push ارسال می‌شود.
        </p>
        <div className="flex justify-end">
          <Button onClick={submit} loading={send.isPending} disabled={!title.trim() || !body.trim()}>
            <Send className="h-4 w-4" /> ارسال اعلان
          </Button>
        </div>
      </Card>
    </div>
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
