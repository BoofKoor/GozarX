// Location name/emoji → ISO alpha-2 country code, for the circular SVG flags in public/flags/.
// The design derives the code from the config remark's regional-indicator emoji (emojiToCC); the
// backend hands us remark NAMES (optionally emoji-prefixed), so we try emoji first, then a keyword
// map, matching location→config by NAME (never index) per the v1 lesson.

const AVAILABLE = new Set(["de", "ua", "us", "tr", "fr", "gb", "nl", "ca"]);

function emojiToCC(s: string): string | null {
  const cps = Array.from(s).map((c) => c.codePointAt(0) ?? 0);
  const ri = cps.filter((cp) => cp >= 0x1f1e6 && cp <= 0x1f1ff);
  if (ri.length >= 2) {
    return String.fromCharCode(ri[0] - 0x1f1e6 + 97, ri[1] - 0x1f1e6 + 97);
  }
  return null;
}

const KEYWORD: Record<string, string> = {
  germany: "de", deutschland: "de", آلمان: "de",
  ukraine: "ua", اوکراین: "ua",
  usa: "us", "united states": "us", america: "us", آمریکا: "us",
  turkey: "tr", türkiye: "tr", ترکیه: "tr",
  france: "fr", فرانسه: "fr",
  uk: "gb", "united kingdom": "gb", britain: "gb", england: "gb", انگلیس: "gb",
  netherlands: "nl", holland: "nl", هلند: "nl",
  canada: "ca", کانادا: "ca",
};

export function flagCC(name: string): string | null {
  const fromEmoji = emojiToCC(name);
  if (fromEmoji && AVAILABLE.has(fromEmoji)) return fromEmoji;
  const key = name.trim().toLowerCase();
  for (const [word, cc] of Object.entries(KEYWORD)) {
    if (key === word || key.includes(word)) return cc;
  }
  return null;
}

// The plain display name (strip a leading flag emoji if the remark carries one).
export function locName(name: string): string {
  return name.replace(/^[\p{Emoji}️\s]+/u, "").trim() || name;
}
