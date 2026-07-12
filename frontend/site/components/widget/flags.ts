// Location name/emoji → ISO alpha-2 country code, for the circular SVG flags in public/flags/.
// The design derives the code from the config remark's regional-indicator emoji (emojiToCC); the
// backend hands us remark NAMES (optionally emoji-prefixed), so we try emoji first, then a keyword
// map, then a bare 2-letter code — matching location→config by NAME (never index) per the v1 lesson.

// Every country we vendor a flag SVG for (public/flags/{cc}.svg). Unknowns fall back to initials.
const AVAILABLE = new Set([
  "de", "ua", "us", "tr", "fr", "gb", "nl", "ca",
  "es", "se", "jp", "au", "ae", "it", "ru", "pl", "ro", "ie", "be", "at",
  "ch", "fi", "dk", "no", "pt", "in", "br", "kr", "sg", "id", "mx", "hu",
]);

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
  turkey: "tr", türkiye: "tr", turkiye: "tr", ترکیه: "tr",
  france: "fr", فرانسه: "fr",
  uk: "gb", "united kingdom": "gb", "u-kingdom": "gb", "u kingdom": "gb", britain: "gb", england: "gb", انگلیس: "gb", انگلستان: "gb",
  netherlands: "nl", holland: "nl", هلند: "nl",
  canada: "ca", کانادا: "ca",
  spain: "es", españa: "es", espana: "es", اسپانیا: "es",
  sweden: "se", سوئد: "se",
  japan: "jp", ژاپن: "jp",
  australia: "au", استرالیا: "au",
  emirates: "ae", uae: "ae", "united arab emirates": "ae", dubai: "ae", امارات: "ae",
  italy: "it", italia: "it", ایتالیا: "it",
  russia: "ru", روسیه: "ru",
  poland: "pl", لهستان: "pl",
  romania: "ro", رومانی: "ro",
  ireland: "ie", ایرلند: "ie",
  belgium: "be", بلژیک: "be",
  austria: "at", اتریش: "at",
  switzerland: "ch", swiss: "ch", سوئیس: "ch",
  finland: "fi", فنلاند: "fi",
  denmark: "dk", دانمارک: "dk",
  norway: "no", نروژ: "no",
  portugal: "pt", پرتغال: "pt",
  india: "in", هند: "in",
  brazil: "br", برزیل: "br",
  "south korea": "kr", korea: "kr", کره: "kr",
  singapore: "sg", سنگاپور: "sg",
  indonesia: "id", اندونزی: "id",
  mexico: "mx", مکزیک: "mx",
  hungary: "hu", مجارستان: "hu",
};

export function flagCC(name: string): string | null {
  // 1) a regional-indicator flag emoji in the remark
  const fromEmoji = emojiToCC(name);
  if (fromEmoji && AVAILABLE.has(fromEmoji)) return fromEmoji;
  const key = locName(name).trim().toLowerCase();
  // 2) a known country keyword (whole word or contained)
  for (const [word, cc] of Object.entries(KEYWORD)) {
    if (key === word || key.includes(word)) return cc;
  }
  // 3) a bare 2-letter code that happens to be a country we vendor (e.g. a remark named just "DE")
  if (/^[a-z]{2}$/.test(key) && AVAILABLE.has(key)) return key;
  return null;
}

// The plain display name (strip a leading flag emoji if the remark carries one).
export function locName(name: string): string {
  return name.replace(/^[\p{Emoji}️\s]+/u, "").trim() || name;
}
