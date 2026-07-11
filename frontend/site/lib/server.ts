import { cookies } from "next/headers";
import { DEFAULT_LOCALE, isLocale, type Locale } from "@/lib/i18n";

// Server-side locale from the cookie (default fa) — used by page server components for their static
// copy so the first render matches the layout's lang/dir.
export async function getLocale(): Promise<Locale> {
  const store = await cookies();
  const raw = store.get("locale")?.value ?? "";
  return isLocale(raw) ? raw : DEFAULT_LOCALE;
}
