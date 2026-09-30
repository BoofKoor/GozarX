"use client";

import { type ReactNode, useEffect, useRef } from "react";
import { type Locale, faDigits, translator } from "@/lib/i18n";
import { Icon } from "@/components/Icon";

// The small modal shell the rewards surfaces share (the rewards card on the account page and the
// missions strip in the claim widget), and the iOS "Add to Home Screen" steps shown in it — iOS
// Safari has no install prompt, and web push only exists there for an installed web app.
export function Overlay({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.focus(); // move focus into the dialog on open
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="overlay open" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal
        tabIndex={-1}
        ref={ref}
        style={{ maxInlineSize: 420 }}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

export function IosSteps({ locale, onClose }: { locale: Locale; onClose: () => void }) {
  const t = translator(locale);
  const steps = [
    { n: 1, text: t("ios_1"), icon: "share" },
    { n: 2, text: t("ios_2"), icon: "download" },
    { n: 3, text: t("ios_3"), icon: "check" },
  ] as const;
  return (
    <Overlay onClose={onClose}>
      <h3 style={{ marginBlockEnd: 12 }}>{t("inst_h")}</h3>
      <div className="ios-steps">
        {steps.map((s) => (
          <div className="ios-step" key={s.n}>
            <span className="ios-n">{faDigits(String(s.n), locale)}</span>
            <span className="ios-t">{s.text}</span>
            <span className="ios-badge">
              <Icon name={s.icon} sw={2} />
            </span>
          </div>
        ))}
      </div>
      <button className="btn ghost block" style={{ marginBlockStart: 14 }} onClick={onClose}>
        {t("common.close")}
      </button>
    </Overlay>
  );
}
