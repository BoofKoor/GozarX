"use client";

import { type Locale, translator } from "@/lib/i18n";
import { type ThemeChoice as Choice, useTheme } from "@/lib/prefs";
import { Icon } from "@/components/Icon";

// The theme control, in the two shapes the site uses: three icon buttons (header, phone menu) and
// three labelled buttons (account settings). Both drive the same `useTheme`, so changing one moves
// the other. "System" comes first — it is the default, and before this control there was no way
// back to it once light or dark had been picked (C-19, decision D6).
const OPTIONS: { value: Choice; icon: string; key: string }[] = [
  { value: "system", icon: "device", key: "theme_sys" },
  { value: "light", icon: "sun", key: "set_theme_l" },
  { value: "dark", icon: "moon", key: "set_theme_d" },
];

export function ThemeChoice({
  locale,
  serverChoice,
  variant,
  className,
}: {
  locale: Locale;
  serverChoice?: Choice;
  variant: "icons" | "labels";
  className?: string;
}) {
  const t = translator(locale);
  const { choice, setChoice } = useTheme(serverChoice);
  return (
    <div
      className={`${variant === "icons" ? "theme-seg" : "mini-seg"}${className ? ` ${className}` : ""}`}
      role="group"
      aria-label={t("set_theme")}
    >
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={choice === o.value}
          aria-label={variant === "icons" ? t(o.key) : undefined}
          title={variant === "icons" ? t(o.key) : undefined}
          onClick={() => setChoice(o.value)}
        >
          {variant === "icons" ? <Icon name={o.icon} sw={2} /> : t(o.key)}
        </button>
      ))}
    </div>
  );
}
