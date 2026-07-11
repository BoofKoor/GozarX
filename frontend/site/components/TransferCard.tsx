"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { type Locale, translator } from "@/lib/i18n";

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
  const [entry, setEntry] = useState("");
  const [restoreErr, setRestoreErr] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (left <= 0) return;
    const id = setInterval(() => setLeft((v) => Math.max(0, v - 1)), 1000);
    return () => clearInterval(id);
  }, [left]);
  useEffect(() => {
    if (left === 0 && code) setCode(null);
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

  async function restore() {
    setRestoreErr(false);
    setBusy(true);
    try {
      const res = await api.redeemTransfer(entry);
      if (res.ok) {
        setMsg(t("transfer.restored"));
        setTimeout(() => window.location.reload(), 900);
      } else {
        setRestoreErr(true);
      }
    } catch {
      setRestoreErr(true);
    } finally {
      setBusy(false);
    }
  }

  async function doReset() {
    setBusy(true);
    try {
      await api.resetDevice();
      window.location.reload();
    } finally {
      setBusy(false);
      setConfirmReset(false);
    }
  }

  return (
    <div className="card card-pad stack">
      <strong>{t("transfer.title")}</strong>
      <p className="hint">{t("transfer.sub")}</p>

      {code ? (
        <div className="stack center">
          <div className="codebox code-lg">{fmt(code)}</div>
          <span className="chip chip-muted tnum">
            {t("transfer.codeExpires")}: {mmss(left)}
          </span>
        </div>
      ) : (
        <button className="btn btn-primary" disabled={busy} onClick={generate}>
          {t("transfer.generate")}
        </button>
      )}

      <hr style={{ border: 0, borderTop: "1px solid var(--border)", margin: "6px 0" }} />

      <strong>{t("transfer.restoreTitle")}</strong>
      <p className="hint">{t("transfer.restoreSub")}</p>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <input
          className={`input codebox${restoreErr ? "" : ""}`}
          style={{ flex: "1 1 200px", direction: "ltr" }}
          placeholder={t("transfer.restorePlaceholder")}
          value={entry}
          onChange={(e) => setEntry(e.target.value)}
          maxLength={9}
        />
        <button className="btn btn-ghost" disabled={busy || !entry} onClick={restore}>
          {t("transfer.restoreBtn")}
        </button>
      </div>
      {restoreErr && <p className="err-text">{t("transfer.badCode")}</p>}
      {msg && <p className="chip chip-success">{msg}</p>}

      <hr style={{ border: 0, borderTop: "1px solid var(--border)", margin: "6px 0" }} />
      <button
        className="btn btn-ghost"
        style={{ color: "var(--danger-ink)" }}
        onClick={() => setConfirmReset(true)}
      >
        {locale === "fa" ? "پاک‌کردن دادهٔ این دستگاه" : "Reset this device's data"}
      </button>

      {confirmReset && (
        <div className="modal-backdrop" onClick={() => setConfirmReset(false)}>
          <div className="modal stack" onClick={(e) => e.stopPropagation()}>
            <strong style={{ fontSize: 18 }}>{locale === "fa" ? "مطمئنی؟" : "Are you sure?"}</strong>
            <p className="muted">
              {locale === "fa"
                ? "همهٔ سوابق، حجم و دعوت‌های این مرورگر پاک می‌شود. برگشت‌پذیر نیست."
                : "All history, volume and invites on this browser will be erased. This can't be undone."}
            </p>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setConfirmReset(false)}>
                {locale === "fa" ? "انصراف" : "Cancel"}
              </button>
              <button className="btn btn-primary" style={{ background: "var(--danger)" }} disabled={busy} onClick={doReset}>
                {locale === "fa" ? "بله، پاک کن" : "Yes, reset"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
