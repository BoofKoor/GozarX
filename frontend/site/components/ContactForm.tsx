"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { Turnstile } from "@/components/Turnstile";
import { Icon } from "@/components/Icon";

// Contact form — faithful reproduction of the design's `.form-card` (topic + message + optional
// reply handle → stored server-side, read from the admin panel). No email/social. The whole card
// flips to `.sent` on success; an empty message shows the `.field.err` inline error.
export function ContactForm({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { config } = useSite();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [emptyErr, setEmptyErr] = useState(false);
  const [sendErr, setSendErr] = useState<string | null>(null);
  const msgRef = useRef<HTMLTextAreaElement>(null);

  const topics = [t("c_t1"), t("c_t2"), t("c_t3"), t("c_t4")];
  const needsTurnstile = !!config?.turnstile_enabled && !!config.turnstile_site_key;
  useEffect(() => {
    if (!needsTurnstile) setToken("");
  }, [needsTurnstile]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSendErr(null);
    if (!message.trim()) {
      setEmptyErr(true);
      msgRef.current?.focus();
      return;
    }
    setEmptyErr(false);
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
      else setSendErr(t("contact.error"));
    } catch {
      setSendErr(t("contact.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={`form-card${sent ? " sent" : ""}`} onSubmit={submit} noValidate>
      <div className="form-body">
        <div className="field">
          <label htmlFor="c-topic">{t("c_topic")}</label>
          <select id="c-topic" className="inp" value={subject} onChange={(e) => setSubject(e.target.value)}>
            <option value="" disabled>
              {t("c_topic_ph")}
            </option>
            {topics.map((tp) => (
              <option key={tp} value={tp}>
                {tp}
              </option>
            ))}
          </select>
        </div>
        <div className={`field${emptyErr ? " err" : ""}`}>
          <label htmlFor="c-msg">{t("c_msg")}</label>
          <textarea
            id="c-msg"
            ref={msgRef}
            className="inp"
            placeholder={t("c_msg_ph")}
            value={message}
            aria-invalid={emptyErr}
            aria-describedby={emptyErr ? "c-msg-err" : undefined}
            onChange={(e) => {
              setMessage(e.target.value);
              if (e.target.value.trim()) setEmptyErr(false);
            }}
            maxLength={5000}
          />
          <span className="errmsg" id="c-msg-err">{t("c_err")}</span>
        </div>
        <div className="field">
          <label htmlFor="c-handle">
            {t("c_handle")} <span className="opt">{t("c_handle_opt")}</span>
          </label>
          <input
            id="c-handle"
            className="inp"
            placeholder={t("c_handle_ph")}
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            maxLength={200}
          />
        </div>
        {needsTurnstile && config && (
          <div className="field">
            <Turnstile siteKey={config.turnstile_site_key} locale={locale} onToken={setToken} />
          </div>
        )}
        {sendErr && <p className="err-text">{sendErr}</p>}
        <button className="btn cta block" disabled={busy || (needsTurnstile && !token)}>
          <Icon name="send" sw={2} cls="ic-dir" />
          {t("c_send")}
        </button>
        <div className="resp-note">
          <Icon name="clock" sw={2} />
          {t("c_resp")}
        </div>
      </div>
      <div className="form-success">
        <div className="ok">
          <Icon name="check" sw={2.6} />
        </div>
        <h3>{t("c_sent_t")}</h3>
        <p>{t("c_sent_p")}</p>
      </div>
    </form>
  );
}
