"use client";

import { type Locale, fill } from "@/lib/i18n";
import { useT } from "@/lib/useT";
import { shareInvite } from "@/lib/rewards";
import { formatMb } from "@/lib/format";
import type { LastConfig } from "@/lib/lastConfig";
import { Icon } from "@/components/Icon";
import { CopyField } from "@/components/widget/pieces";
import "@/styles/claimed.css";

// Everything the claim widget shows only AFTER a claim — the delivered config (copy field, app
// buttons, QR, usage meter, countdown), the missions, the revive and the saved offline config — as
// one module the widget loads on demand (`loadAfter` in ClaimWidget). A first visit sees the picker
// and nothing else, so it no longer downloads these; a tap on the claim button fetches them while
// the claim itself is in flight, and a browser that has held a config fetches them at once.
export { AppButtons, CopyField, Countdown, UsageMeter } from "@/components/widget/pieces";
export { Missions } from "@/components/widget/Missions";
export { QrToggle } from "@/components/widget/QrToggle";

// The last config this browser was shown, while /status cannot be reached. The link itself does not
// depend on this site — an app that imported it keeps connecting — so it is worth handing back even
// when everything else on the page has failed. Past its expiry it says so instead of a date.
export function SavedConfig({ locale, config }: { locale: Locale; config: LastConfig }) {
  const t = useT();
  const until = config.expires_at ? Date.parse(config.expires_at) : NaN;
  const note =
    !Number.isNaN(until) && until > Date.now()
      ? fill(t("offline.until"), {
          t: new Date(until).toLocaleString(locale === "fa" ? "fa-IR" : "en-US", {
            dateStyle: "medium",
            timeStyle: "short",
          }),
        })
      : t("offline.expired");
  return (
    <div className="saved-cfg" data-saved-config>
      <p className="oc-head">
        {t("offline.saved")}
        {config.label && (
          <>
            {" · "}
            <b>{config.label}</b>
          </>
        )}
      </p>
      <CopyField value={config.link} locale={locale} />
      <p className="hint oc-note">{note}</p>
    </div>
  );
}

export function ReviveBlock({
  locale,
  refCode,
  rewardMb,
}: {
  locale: Locale;
  refCode: string;
  rewardMb?: number;
}) {
  const t = useT();
  const link = typeof window !== "undefined" ? `${window.location.origin}/?ref=${refCode}` : "";
  // The link sits in the same framed CopyField as the config link (the bare <code> overflowed the
  // card on a phone); the system share sheet is offered only where one exists — elsewhere a second
  // "copy" button would just repeat the one inside the field.
  const canShare = typeof navigator !== "undefined" && !!navigator.share;
  return (
    <div className="revive">
      <div className="rt">
        <Icon name="spark" sw={2.2} /> {t("revive_t")}
        {rewardMb ? (
          <span className="rv-amt">
            <bdi>+{formatMb(rewardMb, locale)}</bdi>
          </span>
        ) : null}
      </div>
      {/* revive_d is verbatim design copy (a build-time constant in lib/copy/design.ts) with intentional
          <b> emphasis — never user/API data — so rendering it as HTML is safe. */}
      <p className="rd" dangerouslySetInnerHTML={{ __html: t("revive_d") }} />
      <span className="field-label" style={{ marginBlockEnd: 8 }}>
        {t("invite_label")}
      </span>
      <CopyField value={link} locale={locale} />
      {canShare && (
        <button
          type="button"
          className="btn secondary block revive-share"
          onClick={() => void shareInvite(link, t)}
        >
          <Icon name="share" sw={2} /> {t("share")}
        </button>
      )}
    </div>
  );
}
