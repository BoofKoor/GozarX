"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { type Locale, translator } from "@/lib/i18n";
import { Icon } from "@/components/Icon";

// Device transfer — faithful reproduction of the design's `.transfer-card`. Two halves:
//  • Generate: mint a one-time 8-char code (XXXX-XXXX, LTR) with a live mm:ss expiry to move this
//    device's history/volume/invites elsewhere.
//  • Restore: enter a code from another device to bring that history here.
// No login anywhere — identity is device-scoped. Reset lives in the status page's danger row.
function fmt(code: string): string {
  return code.length === 8 ? `${code.slice(0, 4)}-${code.slice(4)}` : code;
}
function mmss(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export function TransferCard({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const [code, setCode] = useState<string | null>(null);
  const [left, setLeft] = useState(0);
  const [copied, setCopied] = useState(false);
  const [entry, setEntry] = useState("");
  const [restoreErr, setRestoreErr] = useState(false);
  const [restored, setRestored] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (left <= 0) {
      if (code) setCode(null);
      return;
    }
    const id = setInterval(() => setLeft((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(id);
  }, [left, code]);

  async function generate() {
    setBusy(true);
    try {
      const res = await api.createTransfer();
      if (res.ok && res.code) {
        setCode(res.code);
        setLeft(res.expires_in ?? 600);
      }
    } finally {
      setBusy(false);
    }
  }

  async function copyCode() {
    if (!code) return;
    try {
      await navigator.clipboard.writeText(fmt(code));
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard blocked */
    }
  }

  async function restore() {
    setRestoreErr(false);
    setBusy(true);
    try {
      const res = await api.redeemTransfer(entry.replace(/-/g, "").trim());
      if (res.ok) {
        setRestored(true);
        setTimeout(() => window.location.reload(), 1000);
      } else {
        setRestoreErr(true);
      }
    } catch {
      setRestoreErr(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card transfer-card">
      {/* Generate side */}
      <div className="th">
        <div className="ti">
          <Icon name="device" sw={2} />
        </div>
        <div>
          <h2>{t("tm_gen_title")}</h2>
        </div>
      </div>
      <p>{t("tm_gen_sub")}</p>
      {code ? (
        <>
          <div className="bigcode" style={{ marginBlockStart: 14 }}>
            <code>{fmt(code)}</code>
            <button className="btn" type="button" onClick={copyCode}>
              {copied ? t("copied") : t("tm_copy")}
            </button>
          </div>
          <div className="expiry">
            <Icon name="clock" sw={2} />
            <span>{t("tm_expiry")}</span> <b>{mmss(left)}</b>
          </div>
        </>
      ) : (
        <button
          className="btn block"
          type="button"
          disabled={busy}
          onClick={generate}
          style={{ marginBlockStart: 14 }}
        >
          <Icon name="device" sw={2} />
          {t("transfer.generate")}
        </button>
      )}

      <hr className="divider" style={{ margin: "18px 0" }} />

      {/* Restore side */}
      <div className="th">
        <div className="ti">
          <Icon name="download" sw={2} />
        </div>
        <div>
          <h2>{t("restore_t")}</h2>
        </div>
      </div>
      <p>{t("restore_d")}</p>
      {restored ? (
        <p className="perm-tag granted" style={{ marginBlockStart: 14, display: "inline-block" }}>
          {t("restored")}
        </p>
      ) : (
        <>
          <div className={`code-input${restoreErr ? " err" : ""}`}>
            <input
              maxLength={9}
              placeholder={t("restore_ph")}
              aria-label={t("restore_ph")}
              value={entry}
              onChange={(e) => {
                setEntry(e.target.value);
                setRestoreErr(false);
              }}
            />
            <button
              className="btn"
              type="button"
              disabled={busy || entry.trim().length < 8}
              onClick={restore}
            >
              <Icon name="check" sw={2.4} />
              {t("restore_btn")}
            </button>
          </div>
          <div className="code-err">{t("restore_err")}</div>
        </>
      )}
    </div>
  );
}
