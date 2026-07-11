"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { Turnstile } from "@/components/Turnstile";

export function ContactForm({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { config } = useSite();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const topics =
    locale === "fa"
      ? ["مشکل در اتصال", "سوال دربارهٔ حجم/دعوت", "گزارش باگ", "پیشنهاد یا سایر"]
      : ["Connection issue", "Question about volume/invites", "Report a bug", "Suggestion or other"];

  const needsTurnstile = !!config?.turnstile_enabled && !!config.turnstile_site_key;

  // Keep the Turnstile token attached to the form; if it's not configured we send without it.
  useEffect(() => {
    if (!needsTurnstile) setToken("");
  }, [needsTurnstile]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!message.trim()) {
      setError(t("contact.emptyErr"));
      return;
    }
    setBusy(true);
    try {
      const res = await api.contact({
        subject: subject || undefined,
        body: message.trim(),
        reply_handle: reply || undefined,
        locale,
        turnstile_token: token || undefined,
      });
      if (res.ok) setSent(true);
      else setError(t("contact.error"));
    } catch {
      setError(t("contact.error"));
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="card card-pad stack center mt-6">
        <span className="chip chip-success" style={{ fontSize: 15 }}>
          ✓ {t("contact.sent")}
        </span>
        <p className="muted">{t("contact.sentSub")}</p>
      </div>
    );
  }

  return (
    <form className="card card-pad stack mt-6" onSubmit={submit}>
      <label className="field">
        <span>{t("contact.topic")}</span>
        <select className="select" value={subject} onChange={(e) => setSubject(e.target.value)}>
          <option value="">—</option>
          {topics.map((tp) => (
            <option key={tp} value={tp}>
              {tp}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>{t("contact.message")}</span>
        <textarea
          className="textarea"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          maxLength={5000}
          required
        />
      </label>
      <label className="field">
        <span>{t("contact.reply")}</span>
        <input
          className="input"
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          placeholder={t("contact.replyPlaceholder")}
          maxLength={200}
        />
      </label>
      {needsTurnstile && config && <Turnstile siteKey={config.turnstile_site_key} onToken={setToken} />}
      {error && <p className="err-text">{error}</p>}
      <button className="btn btn-primary" disabled={busy || (needsTurnstile && !token)}>
        {t("contact.send")}
      </button>
    </form>
  );
}
