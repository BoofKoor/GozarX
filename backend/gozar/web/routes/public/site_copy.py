"""Public site-copy endpoint — the editable hero + homepage-meta strings the marketing site shows.

The four ``site_hero_*`` / ``site_meta_*`` keys live in the ``content`` table, edited from the admin
Texts panel. The site fetches them here at request time (ISR-cached) and falls back to its own
in-code copy when a value is absent or the backend is down — so a fresh/unedited install still
renders, and an admin edit shows without a redeploy. Returns the EXACT locale's value (``null`` when
unset); the locale-specific site supplies the fallback, so an unedited ``en`` request never inherits
the ``fa`` text.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from gozar.db.models.enums import Language
from gozar.services.content import ContentService
from gozar.web.dependencies import DbSession

router = APIRouter(tags=["public"])


class SiteCopyOut(BaseModel):
    hero_title: str | None
    hero_sub: str | None
    meta_title: str | None
    meta_description: str | None


@router.get("/site-copy", response_model=SiteCopyOut)
async def get_site_copy(
    request: Request, session: DbSession, locale: str = Query(default="fa")
) -> SiteCopyOut:
    if locale not in ("fa", "en"):
        raise HTTPException(status_code=422, detail="locale must be 'fa' or 'en'")
    lang = Language(locale)
    content = ContentService(session, request.app.state.redis)
    return SiteCopyOut(
        hero_title=await content.raw("site_hero_title", lang),
        hero_sub=await content.raw("site_hero_sub", lang),
        meta_title=await content.raw("site_meta_title", lang),
        meta_description=await content.raw("site_meta_description", lang),
    )
