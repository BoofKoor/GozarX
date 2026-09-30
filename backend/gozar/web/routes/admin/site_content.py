"""Website copy (auth-gated) — edit the strings the public site shows.

A dedicated surface for the site's own copy, separate from the bot's ``/admin/texts``: only fa/en
(the site has no Russian), grouped the way the homepage reads, and showing the site's in-code
default beside every field so the operator can see what a key currently says and reset it.

Two families live here:

* ``site_hero_*`` / ``site_meta_*`` / ``site_push_*`` — SEEDED keys, kept under their existing
  names so nothing that already reads them changes. The seed writes their default into the row on
  install, so the default is a stored STRING: clearing one writes that string back, and "custom"
  means "differs from it" rather than "non-blank".
* ``site_copy_<designKey>`` — overrides for the allowlisted design-copy strings. An absent or blank
  row means "use the site's in-code copy", which is why clearing a box RESTORES the default instead
  of blanking a heading on the live site.

The two families used to share the second rule, and for a seeded key it is wrong twice over. Every
seeded key read as "custom" on a fresh install (its row is non-blank from day one), each with a
reset button — and the reset stored ``""``, which blanked the homepage's title, meta description
and hero subtitle and made the expired/limited push nudges render as ``[site_push_…]``: a push
has no in-code copy to fall back to.
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


#: The keys whose default is a stored string rather than the absence of a row.
_SEEDED_KEYS = frozenset(k for ks in _SEEDED_GROUPS.values() for k in ks)


def _known() -> dict[str, str]:
    """``{content key: group}`` for everything this editor may touch."""
    keys = {k: group for group, ks in _SEEDED_GROUPS.items() for k in ks}
    keys.update({content_key(k): group for group, ks in SITE_COPY_GROUPS.items() for k in ks})
    return keys


def _defaults(key: str) -> tuple[str, str]:
    if key in _SEEDED_KEYS:
        seeded = DEFAULT_SITE_CONTENT.get(key, {})
        return seeded.get(Language.fa, ""), seeded.get(Language.en, "")
    design = key.removeprefix("site_copy_")
    return default_for(design, Language.fa), default_for(design, Language.en)


def _item(key: str, group: str, fa: str, en: str) -> SiteCopyItem:
    default_fa, default_en = _defaults(key)
    if key in _SEEDED_KEYS:
        overridden = (fa.strip(), en.strip()) != (default_fa.strip(), default_en.strip())
    else:
        overridden = bool(fa.strip() or en.strip())
    return SiteCopyItem(
        key=key,
        group=group,
        fa=fa,
        en=en,
        default_fa=default_fa,
        default_en=default_en,
        overridden=overridden,
    )


@router.get("/", response_model=list[SiteCopyItem])
async def list_site_copy(
    request: Request, session: DbSession, admin: AdminUser
) -> list[SiteCopyItem]:
    rows = await ContentRepository(session).all()
    stored: dict[str, dict[str, str]] = {}
    for row in rows:
        stored.setdefault(row.key, {})[row.language.value] = row.body

    items: list[SiteCopyItem] = []
    # The order the editor shows them in. A group missing here is never listed at all — its keys
    # stay writable but no field offers them — so a new group in SITE_COPY_GROUPS goes here too.
    for group in ("seo", "hero", "widget", "sections", "about", "push"):
        for key, key_group in _known().items():
            if key_group != group:
                continue
            fa = stored.get(key, {}).get("fa", "")
            en = stored.get(key, {}).get("en", "")
            items.append(_item(key, group, fa, en))
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
    default_fa, default_en = _defaults(key)
    for lang, value, default in (
        (Language.fa, body.fa, default_fa),
        (Language.en, body.en, default_en),
    ):
        if value is None:
            continue
        value = value.strip()
        if not value and key in _SEEDED_KEYS:
            # Clearing a seeded key restores its seed default. A blank design-copy row means "use
            # the in-code copy"; a seeded key has none behind it on the push path.
            value = default
        await content.set(key, lang, value, True)

    repo = ContentRepository(session)
    fa = await repo.get_body(key, Language.fa) or ""
    en = await repo.get_body(key, Language.en) or ""
    return _item(key, known[key], fa, en)
