"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { type Locale } from "@/lib/i18n";
import { useT } from "@/lib/useT";
import { useSite } from "@/lib/useSite";
import { Turnstile } from "@/components/Turnstile";
import { Icon } from "@/components/Icon";

// Contact form — faithful reproduction of the design's `.form-card` (topic + message + optional
// reply handle → stored server-side, read from the admin panel). No email/social. The whole card
// flips to `.sent` on success; an empty message shows the `.field.err` inline error.
export function ContactForm({ locale }: { locale: Locale }) {
  const t = useT();
  const { config } = useSite();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [emptyErr, setEmptyErr] = useState(false);
  const [sendErr, setSendErr] = useState<string | null>(null);
  const [tsError, setTsError] = useState(false);
  const [tsReset, setTsReset] = useState(0);
  const msgRef = useRef<HTMLTextAreaElement>(null);
  const sentRef = useRef<HTMLHeadingElement>(null);
  // Stable: <Turnstile> rebuilds the Cloudflare challenge whenever a callback changes identity, and
  // an inline arrow here rebuilt it on every keystroke in the message box.
  const onTsError = useCallback(() => setTsError(true), []);
  // The form body disappears on success, taking the focused button with it — land on the
  // confirmation instead of nowhere, so a screen reader says the message went (C-42).
  useEffect(() => {
    if (sent) sentRef.current?.focus();
  }, [sent]);

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
      // Turnstile tokens are single-use: after any submit, burn the token and reset the widget so a
      // retry gets a fresh one (reusing a consumed token → guaranteed turnstile_failed on retry).
      if (needsTurnstile) {
        setToken("");
        setTsReset((n) => n + 1);
      }
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
            <Turnstile
              siteKey={config.turnstile_site_key}
              locale={locale}
              onToken={setToken}
              onError={onTsError}
              resetSignal={tsReset}
            />
            {tsError && (
              <div className="ts-fail" role="alert">
                <span>
                  <Icon name="warn" sw={2} /> {t("ts_fail")}
                </span>
                <button
                  type="button"
                  className="ts-retry"
                  onClick={() => {
                    setTsError(false);
                    setToken("");
                    setTsReset((n) => n + 1);
                  }}
                >
                  {t("ts_retry")}
                </button>
              </div>
            )}
          </div>
        )}
        {sendErr && (
          <p className="err-text" role="alert">
            {sendErr}
          </p>
        )}
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
        <h2 ref={sentRef} tabIndex={-1}>
          {t("c_sent_t")}
        </h2>
        <p>{t("c_sent_p")}</p>
      </div>
    </form>
  );
}
