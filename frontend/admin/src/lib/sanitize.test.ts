import { describe, expect, it } from "vitest";

import { htmlToText, sanitizeArticleHtml } from "./sanitize";

describe("sanitizeArticleHtml", () => {
  it("keeps the tags a landing article actually uses", () => {
    const html = sanitizeArticleHtml(
      "<h2>عنوان</h2><p>متن <strong>مهم</strong></p><ul><li>یک</li></ul>",
    );
    expect(html).toContain("<h2>عنوان</h2>");
    expect(html).toContain("<strong>مهم</strong>");
    expect(html).toContain("<li>یک</li>");
  });

  it("neutralises anything that could execute in the panel origin", () => {
    // The panel holds the admin JWTs in localStorage, so a pasted body must never run here even
    // though the site treats these rows as trusted content.
    for (const payload of [
      '<img src=x onerror="alert(1)">',
      "<script>alert(1)</script>",
      '<p onclick="alert(1)">hi</p>',
      "<iframe src=//evil></iframe>",
    ]) {
      const out = sanitizeArticleHtml(payload);
      // The payload survives as INERT TEXT (its angle brackets escaped), never as live markup —
      // so an `onerror=` string may still be visible, it just can't be an attribute any more.
      expect(out).not.toMatch(/<(script|img|iframe)/i);
      expect(out).toContain("&lt;");
    }
  });

  it("allows only http(s) links, and opens them safely", () => {
    const ok = sanitizeArticleHtml('<a href="https://example.com">x</a>');
    expect(ok).toContain('rel="noopener noreferrer nofollow"');

    const bad = sanitizeArticleHtml('<a href="javascript:alert(1)">x</a>');
    expect(bad).not.toContain("<a href");
  });

  it("escapes an unclosed or malformed tag instead of emitting it", () => {
    expect(sanitizeArticleHtml("<p")).toBe("&lt;p");
  });
});

describe("htmlToText", () => {
  it("strips markup and collapses whitespace for the word count", () => {
    expect(htmlToText("<p>یک   دو</p>\n<p>سه</p>")).toBe("یک دو سه");
    expect(htmlToText("<p>a&nbsp;b</p>")).toBe("a b");
  });
});
