// Location name/emoji → ISO alpha-2 country code, for the circular SVG flags in public/flags/.
// We vendor the COMPLETE circle-flags country set (public/flags/{cc}.svg), so any code we derive has
// a flag; the <Flag> component still falls back to initials on a missing file (e.g. a non-country
// remark like "WARP"). Order: the remark's flag emoji → a keyword name → a bare 2-letter code —
// matching location→config by NAME (never index) per the v1 lesson.

function emojiToCC(s: string): string | null {
  const cps = Array.from(s).map((c) => c.codePointAt(0) ?? 0);
  const ri = cps.filter((cp) => cp >= 0x1f1e6 && cp <= 0x1f1ff);
  if (ri.length >= 2) {
    return String.fromCharCode(ri[0] - 0x1f1e6 + 97, ri[1] - 0x1f1e6 + 97);
  }
  return null;
}

// Name → code for remarks that carry a plain name (no flag emoji). English + Persian, common
// VPN-endpoint countries. Emoji-prefixed remarks don't need this (emojiToCC covers every country).
const KEYWORD: Record<string, string> = {
  germany: "de", deutschland: "de", آلمان: "de",
  ukraine: "ua", اوکراین: "ua",
  usa: "us", "united states": "us", america: "us", آمریکا: "us",
  turkey: "tr", türkiye: "tr", turkiye: "tr", ترکیه: "tr",
  france: "fr", فرانسه: "fr",
  uk: "gb", "united kingdom": "gb", "u-kingdom": "gb", "u kingdom": "gb", britain: "gb", "great britain": "gb", england: "gb", انگلیس: "gb", انگلستان: "gb", بریتانیا: "gb", "بریتانیا کبیر": "gb",
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
  iran: "ir", ایران: "ir",
  china: "cn", چین: "cn",
  "saudi arabia": "sa", saudi: "sa", عربستان: "sa",
  qatar: "qa", قطر: "qa",
  greece: "gr", یونان: "gr",
  "czech": "cz", czechia: "cz", چک: "cz",
  bulgaria: "bg", بلغارستان: "bg",
  serbia: "rs", صربستان: "rs",
  israel: "il", اسرائیل: "il",
  "hong kong": "hk", hongkong: "hk", "هنگ کنگ": "hk",
  "south africa": "za", "آفریقای جنوبی": "za",
  argentina: "ar", آرژانتین: "ar",
  chile: "cl", شیلی: "cl",
  luxembourg: "lu", لوکزامبورگ: "lu",
  estonia: "ee", latvia: "lv", lithuania: "lt",
  kazakhstan: "kz", قزاقستان: "kz",
  armenia: "am", ارمنستان: "am",
  georgia: "ge", گرجستان: "ge",
  azerbaijan: "az", آذربایجان: "az",
  vietnam: "vn", ویتنام: "vn",
  thailand: "th", تایلند: "th",
  malaysia: "my", مالزی: "my",
  taiwan: "tw", تایوان: "tw",
};

export function flagCC(name: string): string | null {
  // 1) a regional-indicator flag emoji in the remark (covers every country)
  const fromEmoji = emojiToCC(name);
  if (fromEmoji) return fromEmoji;
  const key = locName(name).trim().toLowerCase();
  // 2) a known country keyword (whole word or contained)
  for (const [word, cc] of Object.entries(KEYWORD)) {
    if (key === word || key.includes(word)) return cc;
  }
  // 3) a bare 2-letter code (e.g. a remark named just "DE"); a non-country code 404s → initials
  if (/^[a-z]{2}$/.test(key)) return key;
  return null;
}

// The plain display name (strip a leading flag emoji if the remark carries one).
export function locName(name: string): string {
  return name.replace(/^[\p{Emoji}️\s]+/u, "").trim() || name;
}
