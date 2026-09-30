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
  switzerland: "ch", swiss: "ch", سوئیس: "ch", سوییس: "ch",
  finland: "fi", فنلاند: "fi",
  denmark: "dk", دانمارک: "dk",
  norway: "no", نروژ: "no",
  portugal: "pt", پرتغال: "pt",
  india: "in", هند: "in",
  brazil: "br", برزیل: "br",
  "south korea": "kr", korea: "kr", "کره جنوبی": "kr", کره: "kr",
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
  nigeria: "ng", نیجریه: "ng",
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

// The plain display name (strip a leading flag emoji if the remark carries one). Uses
// Extended_Pictographic + regional-indicator letters, NOT \p{Emoji} — the latter also matches ASCII
// digits, '#' and '*', so a remark like "1. Germany" would lose its leading "1." here (and locName
// is the match key for preselect/popular/landing, so a digit-prefixed remark would silently miss).
export function locName(name: string): string {
  return name.replace(/^[\p{Extended_Pictographic}\p{Regional_Indicator}️\s]+/u, "").trim() || name;
}

// ── display names ──────────────────────────────────────────────────────────────────────────────
// `locName` is the MATCHING key (preselect, popular, landings, `?loc=`) and stays the operator's
// remark. `locLabel` is what a visitor READS: the production remarks are Persian, so the English UI
// said «آلمان، هلند…» (C-44). A remark already in the visitor's script is shown as written — it is
// the operator's wording. Otherwise, when the remark is just a country (a keyword or a bare code,
// optionally numbered: «آلمان ۲»), the country is named in the visitor's language by
// `Intl.DisplayNames`, through a short-form table for the few whose official names don't fit a
// picker card («ایالات متحده» / "United States"). Anything else — a city, a tag — is left alone
// rather than half-translated.

type Lang = "fa" | "en";

const SHORT: Record<Lang, Record<string, string>> = {
  en: { us: "USA", gb: "UK", ae: "UAE", hk: "Hong Kong", kr: "South Korea", cz: "Czechia" },
  fa: { us: "آمریکا", gb: "انگلیس", ae: "امارات", hk: "هنگ‌کنگ", kr: "کره جنوبی", cz: "چک", nl: "هلند" },
};

const ARABIC_SCRIPT = /[؀-ۿ]/;
const LATIN_SCRIPT = /[A-Za-z]/;
// longest first, so «کره جنوبی ۲» is not read as «کره» + «جنوبی ۲», nor "UK 2" as "ukraine"
const BY_LENGTH = Object.entries(KEYWORD).sort((a, b) => b[0].length - a[0].length);
const NUMBERING = /^[\s\d۰-۹٠-٩#.\-–()]*$/;
const regionNames = new Map<Lang, Intl.DisplayNames | null>();

function regionName(cc: string, lang: Lang): string | null {
  const short = SHORT[lang][cc];
  if (short) return short;
  let names = regionNames.get(lang);
  if (names === undefined) {
    try {
      names = new Intl.DisplayNames([lang], { type: "region" });
    } catch {
      names = null;
    }
    regionNames.set(lang, names);
  }
  const name = names?.of(cc.toUpperCase());
  return name && name.toUpperCase() !== cc.toUpperCase() ? name : null;
}

/** The country a remark names, and what is left of it when that is only numbering. */
function countryOf(name: string): { cc: string; rest: string } | null {
  const text = name.trim();
  const key = text.toLowerCase();
  if (/^[a-z]{2}$/.test(key)) return { cc: key, rest: "" };
  for (const [word, cc] of BY_LENGTH) {
    let rest: string | null = null;
    if (key === word) rest = "";
    else if (key.startsWith(word)) rest = text.slice(word.length);
    else if (key.endsWith(word)) rest = text.slice(0, text.length - word.length);
    if (rest !== null && NUMBERING.test(rest)) return { cc, rest: rest.replace(/[()#]/g, "").trim() };
  }
  return null;
}

const toLatinDigits = (s: string) =>
  s.replace(/[۰-۹]/g, (d) => String(d.charCodeAt(0) - 0x06f0)).replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));
const toPersianDigits = (s: string) => s.replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]);

export function locLabel(remark: string, lang: Lang): string {
  const name = locName(remark);
  const bareCode = /^[A-Za-z]{2}$/.test(name.trim()); // "DE" is a code, not a name in any script
  const inScript = lang === "fa" ? ARABIC_SCRIPT.test(name) : LATIN_SCRIPT.test(name) && !ARABIC_SCRIPT.test(name);
  if (inScript && !bareCode) return name;
  const part = countryOf(name);
  const country = part && regionName(part.cc, lang);
  if (!part || !country) return name;
  const rest = lang === "fa" ? toPersianDigits(part.rest) : toLatinDigits(part.rest);
  return rest ? `${country} ${rest}` : country;
}
