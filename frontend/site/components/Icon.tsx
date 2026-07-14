// Line-icon set — verbatim path data from the design artifacts' `IC` map (docs/website/design).
// Mirrors the design's `svg(name, sw, cls)` helper: 24×24 viewBox, stroked, round caps/joins.
// `ic-dir` on directional icons (arrow/send) flips under RTL via globals.css.

export const ICONS: Record<string, string> = {
  bolt: '<path d="M13 2 4.5 13.5H11l-1 8.5 8.5-11.5H12l1-8.5Z"/>',
  check: '<path d="m5 13 4 4L19 7"/>',
  shield:
    '<path d="M12 2 4 5.5V12c0 5 3.5 8.5 8 10 4.5-1.5 8-5 8-10V5.5Z"/><path d="m9 12 2 2 4-4"/>',
  gauge: '<path d="M12 13a3 3 0 0 0 3-3M4 15a8 8 0 1 1 16 0"/>',
  gift: '<rect x="3" y="8" width="18" height="4" rx="1"/><path d="M12 8v13M5 12v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-8M12 8S10.5 3 8 4s0 4 4 4c4 0 6.5-3 4-4s-4 4-4 4Z"/>',
  qr: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3zM19 19h2v2h-2z"/>',
  globe:
    '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  chev: '<path d="m6 9 6 6 6-6"/>',
  chevr: '<path d="m9 6 6 6-6 6"/>',
  flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
  star: '<path d="M12 3.2 14.5 8.3l5.6.8-4 4 .9 5.6-5-2.6-5 2.6.9-5.6-4-4 5.6-.8Z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  users:
    '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0M16 6a3.2 3.2 0 0 1 0 6M18.5 20a5.5 5.5 0 0 0-3-4.9"/>',
  download: '<path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14"/>',
  bell: '<path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6M9.5 20a2.5 2.5 0 0 0 5 0"/>',
  cal: '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>',
  sliders:
    '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
  contrast:
    '<circle cx="12" cy="12" r="9"/><path fill="currentColor" stroke="none" d="M12 3a9 9 0 0 1 0 18Z"/>',
  pin: '<path d="M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11Z"/><circle cx="12" cy="10" r="2.5"/>',
  send: '<path d="m22 2-11 11M22 2 15 22l-4-9-9-4Z"/>',
  spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/>',
  swap: '<path d="M7 4 3 8l4 4M3 8h13M17 20l4-4-4-4M21 16H8"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5 8.6 10.5"/>',
  plug: '<path d="M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0V8ZM12 17v5"/>',
  warn: '<path d="M12 3 2 20h20L12 3Z"/><path d="M12 10v4M12 17v.5"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  device: '<rect x="7" y="3" width="10" height="18" rx="2"/><path d="M11 18h2"/>',
  idcard: '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8" cy="12" r="2.4"/><path d="M13 10h5M13 14h5"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/>',
  trash: '<path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.8.4-1 .9-1 1.7M12 17v.5"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M9 3v14"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
};

export function Icon({
  name,
  sw = 2,
  cls,
}: {
  name: keyof typeof ICONS | string;
  sw?: number;
  cls?: string;
}) {
  const d = ICONS[name] ?? "";
  return (
    <svg
      className={`ic${cls ? " " + cls : ""}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={sw}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      dangerouslySetInnerHTML={{ __html: d }}
    />
  );
}
