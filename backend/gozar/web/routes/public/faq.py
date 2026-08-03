"""Public read endpoint for the site FAQ (``site_faq_items``).

The admin 'website' section authors the rows; the Next.js FAQ page renders them server-side. Like
``pages.py`` this is read-only and open (no device identity, no rate limit) — the site's ISR layer
caches it, so no Redis cache is needed here.

An EMPTY list is a legitimate answer (the operator unpublished everything) but is indistinguishable
from "the seeder hasn't run yet" on the wire, so the site keeps its in-code list as the fallback and
only swaps in these rows when at least one comes back.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from gozar.db.repositories.site_faq_item import SiteFaqItemRepository
from gozar.web.dependencies import DbSession

router = APIRouter(tags=["public"])

_LOCALES = {"fa", "en"}


class FaqItemOut(BaseModel):
    """Deliberately mirrors the site's in-code ``FaqItem`` shape (cat/q/a) so the renderer can take
    either source without a branch."""

    cat: str
    q: str
    a: str


@router.get("/faq", response_model=list[FaqItemOut])
async def list_faq(session: DbSession, locale: str = Query(default="fa")) -> list[FaqItemOut]:
    """Published FAQ items for a locale, in the operator's chosen order."""
    if locale not in _LOCALES:
        raise HTTPException(422, "locale must be 'fa' or 'en'")  # same idiom as public/pages.py
    rows = await SiteFaqItemRepository(session).list_published(locale)
    return [FaqItemOut(cat=i.category, q=i.question, a=i.answer) for i in rows]
