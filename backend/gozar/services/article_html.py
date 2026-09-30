"""Landing-page bodies, made safe to render on the public site.

The site renders a landing body with ``dangerouslySetInnerHTML``, and it is served from the SAME
origin as the admin panel (one nginx, ``/`` and ``/admin/``) — where the admin JWTs live in
``localStorage``. A body carrying ``<img src=x onerror=…>`` therefore ran for every visitor, in the
origin that holds the keys; only the panel's own preview was sanitised.

The algorithm is the panel's (``frontend/admin/src/lib/sanitize.ts``) on purpose, so the preview
shows exactly what the site will: escape EVERYTHING, then re-enable a short allowlist of bare tags
and ``<a href>`` whose target is http(s) or an in-site path. Anything that carries an attribute —
and so could carry a handler — stays escaped, visible as text rather than executed.
"""

from __future__ import annotations

import re

_TAGS = "p|br|h2|h3|h4|ul|ol|li|strong|b|em|i|blockquote|code|pre|hr|small"
_BARE = re.compile(rf"&lt;(/?(?:{_TAGS}))\s*/?&gt;", re.IGNORECASE)
_LINK = re.compile(r"""&lt;a\s+href=(&quot;|"|')([^"'&<>]+)\1&gt;""", re.IGNORECASE)
_LINK_END = re.compile(r"&lt;/a&gt;", re.IGNORECASE)
_EXTERNAL = re.compile(r"^https?://", re.IGNORECASE)
#: Whitespace or a control character. The URL parser drops tabs and newlines ANYWHERE in a link, so
#: `/<TAB>/evil.example` passed as an in-site path and was followed as `//evil.example`.
_HIDDEN = re.compile(r"[\s\x00-\x1f\x7f]")


def _link(match: re.Match[str]) -> str:
    href = match.group(2)
    if _HIDDEN.search(href):
        return match.group(0)
    if _EXTERNAL.match(href):
        return f'<a href="{href}" target="_blank" rel="noopener noreferrer nofollow">'
    # An in-site path — every default landing links to /locations, /faq, /guides. Never `//host`
    # or anything with a backslash: browsers read `/\host` as `//host`, i.e. another site.
    if href.startswith("/") and not href.startswith("//") and "\\" not in href:
        return f'<a href="{href}">'
    return match.group(0)


def sanitize_article_html(raw: str) -> str:
    """``raw`` with everything escaped except the allowlist. Safe to inject as HTML."""
    escaped = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    out = _BARE.sub(lambda m: f"<{m.group(1)}>", escaped)
    out = _LINK.sub(_link, out)
    return _LINK_END.sub("</a>", out)
