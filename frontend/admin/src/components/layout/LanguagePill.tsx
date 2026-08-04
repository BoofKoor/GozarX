import { clsx } from "clsx";

import { useI18n, type Locale } from "@/i18n";

const OPTIONS: { value: Locale; label: string }[] = [
  { value: "fa", label: "فا" },
  { value: "en", label: "EN" },
];

/**
 * The language switch.
 *
 * Both labels are written in their OWN script, never translated — "فا" stays Persian in the English
 * UI and "EN" stays Latin in the Persian one. A language switch that renames its options in the
 * language you are trying to leave is unusable to the person who cannot read it.
 */
export function LanguagePill({ className }: { className?: string }) {
  const { locale, setLocale, t } = useI18n();

  return (
    <div
      role="group"
      aria-label={t("shell.language")}
      className={clsx("flex items-center gap-0.5 rounded-full bg-surface-hover p-0.5", className)}
    >
      {OPTIONS.map((opt) => {
        const active = locale === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => setLocale(opt.value)}
            aria-pressed={active}
            // The labels are proper nouns of their own scripts, so each one is isolated: a Latin
            // "EN" beside a Persian "فا" otherwise reorders the pair in RTL.
            style={{ unicodeBidi: "isolate" }}
            className={clsx(
              "rounded-full px-2.5 py-1 text-xs font-semibold transition",
              active ? "bg-brand text-white shadow-glow" : "text-content-muted hover:text-content",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
