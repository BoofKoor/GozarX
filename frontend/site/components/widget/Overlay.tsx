"use client";

import { type ReactNode, createContext, useContext, useId, useRef } from "react";
import { type Locale, faDigits, translator } from "@/lib/i18n";
import { useFocusTrap } from "@/lib/useFocusTrap";
import { Icon } from "@/components/Icon";

// The dialog's heading id, handed to <OverlayTitle> — a dialog needs a NAME, and `role="dialog"`
// with nothing to label it is announced as "dialog" and nothing else (C-39).
const TitleId = createContext<string | undefined>(undefined);

/** The overlay's heading; names the dialog for assistive tech. */
export function OverlayTitle({ children, style }: { children: ReactNode; style?: React.CSSProperties }) {
  return (
    <h2 className="ov-title" id={useContext(TitleId)} style={style}>
      {children}
    </h2>
  );
}

// The small modal shell the rewards surfaces share (the rewards card on the account page and the
// missions strip in the claim widget), and the iOS "Add to Home Screen" steps shown in it — iOS
// Safari has no install prompt, and web push only exists there for an installed web app. The
// keyboard contract (Esc, focus in and back, Tab kept inside, page scroll locked) is
// `useFocusTrap`'s, shared with the phone menu and the reset confirmation.
export function Overlay({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusTrap(ref, onClose);
  return (
    <div className="overlay open" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal
        aria-labelledby={titleId}
        tabIndex={-1}
        ref={ref}
        style={{ maxInlineSize: 420 }}
        onClick={(e) => e.stopPropagation()}
      >
        <TitleId.Provider value={titleId}>{children}</TitleId.Provider>
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
      <OverlayTitle style={{ marginBlockEnd: 12 }}>{t("inst_h")}</OverlayTitle>
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

// Notifications blocked at the browser level: where to unblock them. Shared by the rewards card's
// push mission and the settings switch, which used to sit disabled with no word of why (C-20).
export function BlockedHint({ locale, onClose }: { locale: Locale; onClose: () => void }) {
  const t = translator(locale);
  return (
    <Overlay onClose={onClose}>
      <div className="push-head">
        <span className="push-ic" style={{ background: "var(--danger-surface)", color: "var(--danger-ink)" }}>
          <Icon name="bell" sw={2} />
        </span>
        <div>
          <OverlayTitle>{t("ps_bl_h")}</OverlayTitle>
          <p className="msub">{t("ps_bl_d")}</p>
        </div>
      </div>
      <p className="hint" dangerouslySetInnerHTML={{ __html: t("ps_bl_hint") }} />
      <button className="btn ghost block" style={{ marginBlockStart: 14 }} onClick={onClose}>
        {t("common.close")}
      </button>
    </Overlay>
  );
}
