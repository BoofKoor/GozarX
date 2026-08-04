import { clsx } from "clsx";

/**
 * An identity circle.
 *
 * The colour is derived from the identifier, not random and not one shared grey: a column of
 * identical circles carries no information and the eye slides straight past it. The four tones are
 * the same validated accents the charts use, so an avatar never introduces a colour the rest of the
 * panel does not already speak.
 */
const TONES = [
  "bg-chart-1 text-white",
  "bg-chart-3 text-white",
  "bg-chart-2 text-white",
  "bg-chart-4 text-white",
];

/** Stable across renders and across pages — the same user is the same colour everywhere. */
function toneFor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return TONES[h % TONES.length];
}

/**
 * Arabic-script names get ONE letter, Latin ones get two.
 *
 * «علی رضایی» → «عر» is not a word, it is two consonants jammed together; Persian interfaces use a
 * single letter, the way Telegram itself does.
 */
export function initialsFor(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return "?";
  if (/[؀-ۿ]/.test(trimmed)) return trimmed[0];
  return trimmed
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

export function Avatar({
  name,
  seed,
  className,
}: {
  name: string;
  /** Overrides what the colour is derived from — use a stable id when the name can change. */
  seed?: string;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={clsx(
        "grid shrink-0 place-items-center rounded-full text-[0.62rem] font-bold",
        // A Latin pair beside Persian text reorders without an isolate.
        toneFor(seed ?? name),
        className ?? "h-8 w-8",
      )}
      style={{ unicodeBidi: "isolate" }}
    >
      {initialsFor(name)}
    </span>
  );
}
