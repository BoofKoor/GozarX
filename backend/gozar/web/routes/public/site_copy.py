"""Public site-copy endpoint — the editable strings the marketing site shows.

The four ``site_hero_*`` / ``site_meta_*`` keys live in the ``content`` table, edited from the admin
panel. ``overrides`` carries the wider set of design-copy overrides (``site_copy_<designKey>``
rows), so any allowlisted homepage string can be changed from the panel without a redeploy.

The site fetches this at request time (ISR-cached) and falls back to its own in-code copy when a
value is absent or the backend is down — so a fresh/unedited install and a backend outage both
render exactly the same as before this endpoint existed. Returns the EXACT locale's value (``null``
when unset); the locale-specific site supplies the fallback, so an unedited ``en`` request never
inherits the ``fa`` text.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from gozar.db.models.enums import Language
from gozar.services.content import ContentService
from gozar.services.site_copy_keys import SITE_COPY_KEYS, content_key
from gozar.web.dependencies import DbSession

router = APIRouter(tags=["public"])


class SiteCopyOut(BaseModel):
    hero_title: str | None
    hero_sub: str | None
    meta_title: str | None
    meta_description: str | None
    # design-copy key -> override. Only keys the operator has actually customised appear; the site
    # never depends on a key being present. Named `overrides`, not `copy`, because a pydantic field
    # called `copy` shadows BaseModel.copy().
    overrides: dict[str, str]


@router.get("/site-copy", response_model=SiteCopyOut)
async def get_site_copy(
    request: Request, session: DbSession, locale: str = Query(default="fa")
) -> SiteCopyOut:
    if locale not in ("fa", "en"):
        raise HTTPException(status_code=422, detail="locale must be 'fa' or 'en'")
    lang = Language(locale)
    content = ContentService(session, request.app.state.redis)

    overrides: dict[str, str] = {}
    for key in SITE_COPY_KEYS:
        value = await content.raw(content_key(key), lang)
        # A blank row is treated as "not overridden" rather than "show nothing" — clearing a box in
        # the panel must restore the in-code copy, not blank out a heading on the live site.
        if value and value.strip():
            overrides[key] = value

    return SiteCopyOut(
        hero_title=await content.raw("site_hero_title", lang),
        hero_sub=await content.raw("site_hero_sub", lang),
        meta_title=await content.raw("site_meta_title", lang),
        meta_description=await content.raw("site_meta_description", lang),
        overrides=overrides,
    )
