// A conservative HTML allowlist for previewing admin-authored landing-page bodies.
//
// The public site renders these rows with `dangerouslySetInnerHTML` (they are trusted, admin-only
// content). The PANEL is a different matter: it holds the admin JWTs in localStorage, so pasting a
// body containing `<img onerror=…>` and hitting preview must not be able to run anything in this
// origin. Everything is escaped first, then only the small tag set a landing article actually needs
// is re-enabled — the same shape as `telegramPreviewHtml` in lib/format.ts.

// Block + inline tags a keyword landing legitimately uses. Attribute-less; `<a href>` is handled
// separately so the scheme can be checked.
const TAGS = "p|br|h2|h3|h4|ul|ol|li|strong|b|em|i|blockquote|code|pre|hr|small";

/** Escape everything, then re-enable the allowlisted subset. Returns HTML safe to inject. */
export function sanitizeArticleHtml(raw: string): string {
  const escaped = raw.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return (
    escaped
      // Opening/closing tags with no attributes at all — anything carrying an attribute (and
      // therefore a possible event handler) stays escaped and visible as text.
      .replace(new RegExp(`&lt;(/?(?:${TAGS}))\\s*/?&gt;`, "gi"), "<$1>")
      // Links: only http(s), and always opened safely.
      .replace(/&lt;a\s+href=(&quot;|"|')([^"'&<>]+)\1&gt;/gi, (m, _q, href) =>
        /^https?:\/\//i.test(href)
          ? `<a href="${href}" target="_blank" rel="noopener noreferrer nofollow">`
          : m,
      )
      .replace(/&lt;\/a&gt;/gi, "</a>")
  );
}

/** Plain text of an HTML body — used for the reading-length estimate in the SEO checklist. */
export function htmlToText(raw: string): string {
  return raw
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
