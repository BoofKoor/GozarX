import type { Metadata } from "next";
import { cookies, headers } from "next/headers";
import "@/styles/tokens.css";
import "@/styles/base.css";
import { LOCALE_COOKIE, pickLocale } from "@/lib/locale";
import { translator } from "@/lib/copy";
import { SiteDocument } from "@/components/SiteDocument";
import { NotFoundBody } from "@/components/NotFoundBody";

// A path no route claims. The root layout lives inside `app/[lang]` (one tree per language), so there
// is no app-wide layout for Next to draw a 404 in: this draws the whole document itself, with the
// same SiteDocument the layout uses, in the language `proxy.ts` would have picked. Rendered per
// request and never cached — a scanner walking made-up URLs must not fill the page cache with 404s.
// (A catch-all route in its place answered 404 too, but Next could only render its notFound() in
// the browser: the HTML was an empty error shell, where main had served the whole 404 page.)
async function locale() {
  return pickLocale((await cookies()).get(LOCALE_COOKIE)?.value, (await headers()).get("accept-language"));
}

export async function generateMetadata(): Promise<Metadata> {
  return { title: `${translator(await locale())("notfound.title")} — GozarX` };
}

export default async function GlobalNotFound() {
  return (
    <SiteDocument locale={await locale()}>
      <NotFoundBody />
    </SiteDocument>
  );
}
