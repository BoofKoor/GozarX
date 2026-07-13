// The site's canonical public origin — the single source for absolute URLs in the page metadata,
// the sitemap, robots.txt, and Open Graph tags. Defaults to the production domain so the build needs
// zero configuration; override with the SITE_URL env var (baked at build time in
// docker/Dockerfile.site) for a different-domain deployment. Any trailing slash is trimmed so
// `${SITE_URL}${path}` is always well-formed.
export const SITE_URL = (process.env.SITE_URL ?? "https://gozarx.gozarxservices.com").replace(
  /\/+$/,
  "",
);

// Google Search Console "HTML tag" verification token. Optional: when unset (the default), no
// verification <meta> is emitted — verify the property via DNS/Cloudflare instead. To use the tag
// method, set GOOGLE_SITE_VERIFICATION to the content value shown by Search Console for a
// URL-prefix property → "HTML tag".
export const GOOGLE_SITE_VERIFICATION = process.env.GOOGLE_SITE_VERIFICATION || undefined;
