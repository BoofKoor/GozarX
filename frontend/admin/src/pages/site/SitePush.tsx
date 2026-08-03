import { Send, Users as UsersIcon } from "lucide-react";
import { type ReactNode, useState } from "react";
import { toast } from "sonner";

import { SiteTabs } from "@/components/site/SiteTabs";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useConfirm } from "@/components/ui/confirm";
import { PageHeader } from "@/components/ui/PageHeader";
import { useSendSitePush, useSitePushAudience } from "@/hooks/useSite";
import { apiErrorMessage } from "@/lib/api";
import { formatNumber } from "@/lib/format";

export function SitePush() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [url, setUrl] = useState("");
  const { data: audience, isError: audienceError } = useSitePushAudience();
  const send = useSendSitePush();
  const confirm = useConfirm();
  const recipients = audience?.recipients;

  async function submit() {
    const t = title.trim();
    const b = body.trim();
    if (!t || !b) return;
    const ok = await confirm({
      title: "ارسال اعلان",
      message: `این اعلان به ${formatNumber(recipients ?? 0)} دستگاه ارسال شود؟`,
      confirmLabel: "ارسال",
    });
    if (!ok) return;
    send.mutate(
      { title: t, body: b, url: url.trim() },
      {
        onSuccess: (r) => {
          toast.success(`در صف ارسال به ${r.recipients} دستگاه قرار گرفت.`);
          setTitle("");
          setBody("");
          setUrl("");
        },
        onError: (err) => toast.error(apiErrorMessage(err, "ارسال نشد.")),
      },
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="وب‌سایت" />
      <SiteTabs />

      <Card className="max-w-2xl space-y-4">
        <div className="flex items-center gap-2 text-sm text-content-muted">
          <UsersIcon className="h-4 w-4" />
          گیرندگان:{" "}
          <span className="font-bold text-brand">
            {recipients ?? (audienceError ? "—" : "…")}
          </span>{" "}
          دستگاهِ مشترک
        </div>
        <Field label="عنوان اعلان">
          <input
            className="field-control"
            dir="auto"
            maxLength={120}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </Field>
        <Field label="متن اعلان">
          <textarea
            className="field-control min-h-[120px]"
            dir="auto"
            maxLength={300}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </Field>
        <Field label="لینک مقصد (اختیاری)">
          <input
            className="field-control"
            dir="ltr"
            maxLength={512}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="/status"
          />
        </Field>
        <p className="text-xs text-content-subtle">
          اعلان در پس‌زمینه (arq worker) به همهٔ دستگاه‌های مشترکِ Web Push ارسال می‌شود.
        </p>
        <div className="flex justify-end">
          <Button
            onClick={submit}
            loading={send.isPending}
            disabled={!title.trim() || !body.trim()}
          >
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
