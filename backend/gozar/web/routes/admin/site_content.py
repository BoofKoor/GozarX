"""Website copy (auth-gated) — edit the strings the public site shows.

A dedicated surface for the site's own copy, separate from the bot's ``/admin/texts``: only fa/en
(the site has no Russian), grouped the way the homepage reads, and showing the site's in-code
default beside every field so the operator can see what a key currently says and reset it.

Two families live here:

* ``site_hero_*`` / ``site_meta_*`` — the original four keys, kept under their existing names so
  nothing that already reads them changes.
* ``site_copy_<designKey>`` — overrides for the allowlisted design-copy strings. An absent or blank
  row means "use the site's in-code copy", which is why clearing a box RESTORES the default instead
  of blanking a heading on the live site.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from gozar.db.models.enums import Language
from gozar.db.repositories.content import ContentRepository
from gozar.seed import DEFAULT_SITE_CONTENT
from gozar.services.content import ContentService
from gozar.services.site_copy_keys import (
    SITE_COPY_GROUPS,
    content_key,
    default_for,
)
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/site/content", tags=["site-content"])

# The seeded site keys that are NOT design-copy overrides, grouped for the editor. The push strings
# are server-sent nudges rather than page copy, so they get their own group.
_SEEDED_GROUPS: dict[str, list[str]] = {
    "seo": ["site_meta_title", "site_meta_description"],
    "hero": ["site_hero_title", "site_hero_sub"],
    "push": [
        "site_push_expired_title",
        "site_push_expired_body",
        "site_push_limited_title",
        "site_push_limited_body",
    ],
}

GROUP_LABELS = {
    "seo": "متا و سئو",
    "hero": "هدر اصلی",
    "widget": "ویجت دریافت کانفیگ",
    "sections": "بخش‌های صفحهٔ اصلی",
    "push": "متن اعلان‌های خودکار",
}


class SiteCopyItem(BaseModel):
    key: str  # the content-table row name
    group: str
    fa: str
    en: str
    # What the site renders when the row is blank. For a design-copy override this is the in-code
    # string; for a seeded key it's the seed default.
    default_fa: str
    default_en: str
    overridden: bool


class SiteCopyPatch(BaseModel):
    fa: str | None = None
    en: str | None = None


def _known() -> dict[str, str]:
    """``{content key: group}`` for everything this editor may touch."""
    keys = {k: group for group, ks in _SEEDED_GROUPS.items() for k in ks}
    keys.update({content_key(k): group for group, ks in SITE_COPY_GROUPS.items() for k in ks})
    return keys


def _defaults(key: str, group: str) -> tuple[str, str]:
    if key in {k for ks in _SEEDED_GROUPS.values() for k in ks}:
        seeded = DEFAULT_SITE_CONTENT.get(key, {})
        return seeded.get(Language.fa, ""), seeded.get(Language.en, "")
    design = key.removeprefix("site_copy_")
    return default_for(design, Language.fa), default_for(design, Language.en)


@router.get("/", response_model=list[SiteCopyItem])
async def list_site_copy(
    request: Request, session: DbSession, admin: AdminUser
) -> list[SiteCopyItem]:
    rows = await ContentRepository(session).all()
    stored: dict[str, dict[str, str]] = {}
    for row in rows:
        stored.setdefault(row.key, {})[row.language.value] = row.body

    items: list[SiteCopyItem] = []
    for group in ("seo", "hero", "widget", "sections", "push"):
        for key, key_group in _known().items():
            if key_group != group:
                continue
            default_fa, default_en = _defaults(key, group)
            fa = stored.get(key, {}).get("fa", "")
            en = stored.get(key, {}).get("en", "")
            items.append(
                SiteCopyItem(
                    key=key,
                    group=group,
                    fa=fa,
                    en=en,
                    default_fa=default_fa,
                    default_en=default_en,
                    overridden=bool(fa.strip() or en.strip()),
                )
            )
    return items


@router.put("/{key}", response_model=SiteCopyItem)
async def update_site_copy(
    key: str, body: SiteCopyPatch, request: Request, session: DbSession, admin: AdminUser
) -> SiteCopyItem:
    """Set (or clear) one string.

    Only allowlisted keys are writable — this endpoint must never become a way to write arbitrary
    rows into the shared ``content`` table.
    """
    known = _known()
    if key not in known:
        raise HTTPException(404, "unknown site copy key")

    content = ContentService(session, request.app.state.redis)
    for lang, value in ((Language.fa, body.fa), (Language.en, body.en)):
        if value is not None:
            # An empty string is stored as-is; the public endpoint treats a blank row as "not
            # overridden", so clearing the box is how the operator reverts to the site's own copy.
            await content.set(key, lang, value.strip(), True)

    rows = [r for r in await ContentRepository(session).all() if r.key == key]
    fa = next((r.body for r in rows if r.language is Language.fa), "")
    en = next((r.body for r in rows if r.language is Language.en), "")
    default_fa, default_en = _defaults(key, known[key])
    return SiteCopyItem(
        key=key,
        group=known[key],
        fa=fa,
        en=en,
        default_fa=default_fa,
        default_en=default_en,
        overridden=bool(fa.strip() or en.strip()),
    )
