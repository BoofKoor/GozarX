import { readFile } from "node:fs/promises";
import path from "node:path";
import { ImageResponse } from "next/og";
import { fetchLanding } from "@/lib/landing";
import { SITE_URL } from "@/lib/site";
import { flagCC } from "@/components/widget/flags";
import { LOGO_ACCENT, LOGO_MAIN } from "@/components/LogoSymbol";

// The social card (C-66): `/og/site.png` for the site, `/og/<slug>.png` for a location landing, with
// that country's flag. Every share used to show the 512px square app icon, which a large preview
// (Telegram, X, WhatsApp) crops to a sliver. 1200×630, the size those previews are laid out for.
//
// Latin only, by design: the renderer (Satori) does not shape Arabic script, so Persian here would
// come out as disconnected letters. The page's own title rides beside the card in every preview.
//
// Outside `[lang]` and ending in `.png`, so `proxy.ts` leaves it alone. Cached like the pages — the
// first request renders it, and it is rebuilt at most daily (a flag does not change often).
export const revalidate = 86400;

export function generateStaticParams(): { name: string }[] {
  return [];
}

const SIZE = { width: 1200, height: 630 };

async function flagUri(cc: string): Promise<string | null> {
  try {
    const svg = await readFile(path.join(process.cwd(), "public", "flags", `${cc}.svg`));
    return `data:image/svg+xml;base64,${svg.toString("base64")}`;
  } catch {
    return null;
  }
}

export async function GET(_req: Request, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  let flag: string | null = null;
  if (name !== "site.png") {
    const slug = name.match(/^([a-z0-9][a-z0-9-]{0,99})\.png$/)?.[1];
    const row = slug ? await fetchLanding(slug, "fa") : null;
    if (!row) return new Response("Not found", { status: 404 });
    const cc = row.location_remark ? flagCC(row.location_remark) : null;
    flag = cc ? await flagUri(cc) : null;
  }
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 96px",
          color: "#fff",
          backgroundColor: "#0B1220",
          backgroundImage:
            "radial-gradient(circle at 88% 12%, rgba(34,211,238,.38), transparent 46%), linear-gradient(135deg, #0B1220 0%, #12306E 58%, #0E5A78 100%)",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center" }}>
            <svg width="170" height="135" viewBox="0 0 639 508">
              <path fill="#FFFFFF" d={LOGO_MAIN} />
              <path fill="#60A5FA" d={LOGO_ACCENT} />
            </svg>
            <span style={{ fontSize: 118, marginLeft: 34, letterSpacing: -3 }}>GozarX</span>
          </div>
          <span style={{ fontSize: 34, marginTop: 30, color: "#BFDBFE" }}>{new URL(SITE_URL).host}</span>
        </div>
        {flag && (
          <img
            src={flag}
            width={300}
            height={300}
            alt=""
            style={{ borderRadius: 9999, border: "12px solid rgba(255,255,255,.92)" }}
          />
        )}
      </div>
    ),
    SIZE,
  );
}
