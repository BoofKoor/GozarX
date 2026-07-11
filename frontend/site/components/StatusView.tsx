"use client";

import { type Locale, translator } from "@/lib/i18n";
import { useSite } from "@/lib/useSite";
import { ClaimWidget } from "@/components/ClaimWidget";
import { TransferCard } from "@/components/TransferCard";

export function StatusView({ locale }: { locale: Locale }) {
  const t = translator(locale);
  const { status, loading, offline } = useSite();

  const pct =
    status && status.daily_limit_bytes > 0
      ? Math.min(100, Math.round((status.usage_bytes / status.daily_limit_bytes) * 100))
      : 0;

  return (
    <div className="stack mt-4">
      {offline && (
        <div className="card card-pad" style={{ borderColor: "var(--warning)" }}>
          <span className="chip chip-warning">{t("status.offline")}</span>
        </div>
      )}

      <div className="stat-row">
        <Stat k={t("status.usage")} v={loading ? "…" : (status?.usage ?? "—")} />
        <Stat k={t("status.remaining")} v={loading ? "…" : (status?.remaining ?? "—")} />
        <Stat k={t("status.dailyLimit")} v={loading ? "…" : (status?.daily_limit ?? "—")} />
        <Stat
          k={t("status.invites")}
          v={status ? `${status.referral_count}/${status.referral_cap}` : "—"}
        />
        <Stat
          k={t("status.streak")}
          v={status ? `${status.streak_count}/${status.streak_days}` : "—"}
        />
      </div>

      <div className="meter" aria-hidden>
        <i style={{ width: `${pct}%` }} />
      </div>

      <ClaimWidget locale={locale} />

      <TransferCard locale={locale} />
    </div>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div className="stat">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
    </div>
  );
}
