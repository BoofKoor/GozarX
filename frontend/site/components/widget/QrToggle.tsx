"use client";

import { useId, useState } from "react";
import { type Locale, translator } from "@/lib/i18n";
import { Icon } from "@/components/Icon";

// The config link as a QR code (C-09, decision D5) — for the case the copy button cannot serve: the
// config claimed on a laptop, the app on the phone. The copy promised «QR را اسکن کن» and there was
// no QR anywhere. The encoder (uqr, ~12 KB) loads on the first open, so a visitor who never asks
// for it downloads nothing. Drawn as ONE SVG path, black on white in both themes: scanners want
// dark modules on a light ground, and an inverted code is exactly the one many of them miss. The
// quiet zone is the spec's four modules.
export function QrToggle({ value, locale }: { value: string; locale: Locale }) {
  const t = translator(locale);
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState<{ size: number; path: string; for: string } | null>(null);
  const [failed, setFailed] = useState(false);
  const panelId = useId();

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (!next || code?.for === value) return;
    try {
      const { encode } = await import("uqr");
      const qr = encode(value, { ecc: "M", border: 4 });
      let path = "";
      qr.data.forEach((row, y) =>
        row.forEach((dark, x) => {
          if (dark) path += `M${x} ${y}h1v1h-1z`;
        }),
      );
      setCode({ size: qr.size, path, for: value });
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }

  const ready = code?.for === value ? code : null;
  return (
    <>
      <div className="cfg-actions">
        <button
          type="button"
          className="icon-btn"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={toggle}
        >
          <Icon name="qr" sw={2} />
          {open ? t("hide_qr") : t("show_qr")}
        </button>
      </div>
      <div id={panelId} className={`qr-panel${open ? " show" : ""}`} hidden={!open}>
        {ready ? (
          <figure className="qr-fig">
            <span className="qr-box">
              <svg
                viewBox={`0 0 ${ready.size} ${ready.size}`}
                role="img"
                aria-label={t("qr_alt")}
                shapeRendering="crispEdges"
              >
                <rect width={ready.size} height={ready.size} fill="#fff" />
                <path d={ready.path} fill="#000" />
              </svg>
            </span>
            <figcaption className="hint">{t("qr_hint")}</figcaption>
          </figure>
        ) : failed ? (
          <p className="hint" role="alert">
            {t("qr_failed")}
          </p>
        ) : (
          <span className="qr-box qr-wait skeleton" aria-hidden />
        )}
      </div>
    </>
  );
}
