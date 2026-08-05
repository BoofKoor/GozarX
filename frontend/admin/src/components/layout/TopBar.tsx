import { clsx } from "clsx";
import { Menu, Search } from "lucide-react";
import { Link } from "react-router-dom";

import { useI18n, type MessageKey } from "@/i18n";
import { useSystemHealth } from "@/hooks/useSystem";
import { getUsername } from "@/lib/auth";

import { useChrome } from "./chrome";
import { LanguagePill } from "./LanguagePill";
import { ThemeToggle } from "./ThemeToggle";

const STATUS: Record<string, { tone: string; key: MessageKey }> = {
  ok: { tone: "bg-success-500", key: "shell.health.ok" },
  degraded: { tone: "bg-warning-500", key: "shell.health.degraded" },
  down: { tone: "bg-danger-500", key: "shell.health.down" },
};

/** Live status dot linking to the System page — the health snapshot is already polled every 10s
 *  there, and react-query shares the one query, so this costs no extra requests. */
function HealthDot() {
  const { data } = useSystemHealth();
  const { t } = useI18n();
  const state = STATUS[data?.status ?? ""];
  const label = t(state?.key ?? "shell.health.checking");
  const tone = state?.tone ?? "bg-content-subtle";
  return (
    <Link
      to="/system"
      title={label}
      aria-label={label}
      className="flex h-9 w-9 items-center justify-center rounded-xl transition hover:bg-surface-hover"
    >
      <span className="relative flex h-2.5 w-2.5">
        {data?.status === "ok" && (
          <span
            className={clsx(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-70",
              tone,
            )}
          />
        )}
        <span className={clsx("relative inline-flex h-2.5 w-2.5 rounded-full", tone)} />
      </span>
    </Link>
  );
}

export function TopBar({
  onMenuClick,
  onSearchClick,
}: {
  onMenuClick: () => void;
  onSearchClick: () => void;
}) {
  const { t } = useI18n();
  const username = getUsername() ?? "admin";
  const initial = username.charAt(0).toUpperCase();
  const chrome = useChrome();

  return (
    // On the well, not on its own surface: the design's top bar is the first row INSIDE the content
    // column, so the page starts where the well starts. As a separate `bg-nav` strip with a rule
    // under it, the console spent two horizontal bands and ~105px saying its own name — once here
    // and once again in the page header a line below.
    <header className="sticky top-0 z-30 flex items-center gap-3 bg-surface-sunken px-4 pb-2 pt-3 sm:px-5">
      <button
        onClick={onMenuClick}
        aria-label={t("shell.openMenu")}
        className="-ms-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-content-muted transition hover:bg-surface-hover hover:text-content md:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Filled by whichever page is mounted, through <PageHeader>. */}
      <div ref={chrome?.setTitleHost} className="min-w-0 flex-1" />

      <div className="flex shrink-0 items-center gap-1.5">
        <button
          onClick={onSearchClick}
          aria-label={t("shell.searchAria")}
          className="flex h-9 items-center gap-2 rounded-xl border border-line px-2.5 text-xs text-content-subtle transition hover:bg-surface-hover hover:text-content"
        >
          <Search className="h-4 w-4" />
          <span className="hidden sm:inline">{t("shell.search")}</span>
          <kbd
            className="hidden rounded border border-line px-1 py-0.5 text-[10px] sm:inline"
            // A Latin shortcut inside an RTL bar reorders without an isolate.
            style={{ unicodeBidi: "isolate" }}
            dir="ltr"
          >
            ⌘K
          </kbd>
        </button>
        <LanguagePill className="hidden sm:flex" />
        <HealthDot />
        <ThemeToggle />
        {/* Sign-out lives on the rail's far end, where the mock puts it — repeating it here made
            the busiest corner of the panel carry two ways to leave. */}
        <div
          className="hidden h-8 w-8 items-center justify-center rounded-full bg-brand text-[11px] font-bold text-white sm:flex"
          title={username}
        >
          {initial}
        </div>
      </div>
    </header>
  );
}
