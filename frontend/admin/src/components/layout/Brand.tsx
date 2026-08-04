import { clsx } from "clsx";

import { useI18n } from "@/i18n";

// The real GozarX mark — paths verbatim from the shared asset (frontend/site/public/logo-mark.svg
// and docs/website/design/assets/logo-mark.svg). The main body uses the ink colour, the trailing
// "X" stroke uses the brand accent, exactly like the site's LogoSymbol.
const MAIN =
  "M403.076 96.9894L452.145 12C455.224 6.66672 451.375 0 445.217 0H151.172C148.314 0 145.673 1.52478 144.244 3.99999L2.3094 249.838C0.880339 252.313 0.880333 255.363 2.3094 257.838L144.244 503.676C145.673 506.151 148.314 507.676 151.172 507.676H445.287C451.445 507.676 455.294 501.01 452.215 495.676L319.518 265.838C316.439 260.505 308.741 260.505 305.662 265.838L255.311 353.048C253.882 355.523 253.882 358.573 255.311 361.048L274.733 394.687C277.812 400.02 273.963 406.687 267.804 406.687H212.584C209.725 406.687 207.084 405.162 205.655 402.687L122.027 257.838C120.598 255.363 120.598 252.313 122.027 249.838L205.655 104.989C207.084 102.514 209.725 100.989 212.584 100.989H396.147C399.006 100.989 401.647 99.4646 403.076 96.9894Z";
const ACCENT =
  "M624.832 0H523.233C520.364 0 517.714 1.53705 516.289 4.02804L375.687 249.847C374.274 252.318 374.28 255.354 375.703 257.819L517.648 503.675C519.077 506.15 521.718 507.675 524.576 507.675H624.832C630.99 507.675 634.839 501.008 631.76 495.675L494.444 257.838C493.015 255.363 493.015 252.313 494.444 249.838L631.76 12C634.84 6.66667 630.991 0 624.832 0Z";

/**
 * The bare mark, in the brand colour.
 *
 * This is what the navigation rail carries: a tile there would be a second filled square in a
 * column of outlined ones, reading as another destination rather than as identity.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 639 508" className={clsx("text-brand", className)} fill="none" aria-hidden>
      <path d={MAIN} fill="currentColor" />
      <path d={ACCENT} fill="currentColor" fillOpacity={0.55} />
    </svg>
  );
}

/** The mark on a brand-blue tile — for the login card, where it is the page's only anchor. */
export function BrandTile({ className }: { className?: string }) {
  return (
    <span
      className={clsx(
        "flex items-center justify-center rounded-xl bg-brand text-white shadow-glow",
        className,
      )}
      aria-hidden
    >
      <svg viewBox="0 0 639 508" className="h-[52%] w-[52%]" fill="none">
        <path d={MAIN} fill="currentColor" />
        <path d={ACCENT} fill="currentColor" fillOpacity={0.72} />
      </svg>
    </span>
  );
}

/** Drawer/login lockup: tile + wordmark. `compact` hides the text. */
export function BrandLockup({
  compact = false,
  sub,
  className,
}: {
  compact?: boolean;
  sub?: string;
  className?: string;
}) {
  const { t } = useI18n();
  return (
    <div className={clsx("flex items-center gap-2.5", className)}>
      <BrandTile className="h-9 w-9 shrink-0" />
      {!compact && (
        <div className="min-w-0 leading-tight">
          {/* The wordmark is a proper noun: it stays Latin in both languages, and is isolated so a
              Persian subtitle beneath it cannot reorder it. */}
          <div
            className="truncate text-base font-bold text-content"
            style={{ unicodeBidi: "isolate" }}
          >
            GozarX
          </div>
          <div className="truncate text-[11px] text-content-subtle">{sub ?? t("shell.title")}</div>
        </div>
      )}
    </div>
  );
}
