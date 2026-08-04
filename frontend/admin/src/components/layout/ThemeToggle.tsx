import { Moon, Sun } from "lucide-react";
import { useEffect } from "react";

import { useTheme } from "@/hooks/useTheme";
import { useI18n } from "@/i18n";

/** Light/dark toggle for the top bar, plus a global Shift+D shortcut. The shortcut is ignored while
 *  a text field is focused so it never fights with typing. */
export function ThemeToggle() {
  const { isDark, toggle } = useTheme();
  const { t } = useI18n();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.shiftKey || (e.key !== "D" && e.key !== "d")) return;
      const el = document.activeElement;
      const tag = el?.tagName;
      const typing =
        tag === "INPUT" || tag === "TEXTAREA" || (el as HTMLElement | null)?.isContentEditable;
      if (typing) return;
      e.preventDefault();
      toggle();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [toggle]);

  return (
    <button
      onClick={toggle}
      aria-label={isDark ? t("shell.theme.toLight") : t("shell.theme.toDark")}
      title={t("shell.theme.title")}
      className="flex h-9 w-9 items-center justify-center rounded-xl text-content-muted transition hover:bg-surface-hover hover:text-content"
    >
      {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
    </button>
  );
}
