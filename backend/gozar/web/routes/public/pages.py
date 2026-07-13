"""Public read endpoints for the SEO keyword landings (``site_landing_pages``).

The admin 'website' section authors the rows (JWT-gated CRUD in ``admin/landing.py``); the Next.js
site renders them server-side at ``/l/{slug}`` and lists them in the sitemap / locations index.
Read-only and open (no device identity, no rate limit — same shape as ``GET /config``); the site's
ISR layer caches responses, so no Redis cache is needed here.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel

from gozar.db.models.site_landing_page import SiteLandingPage
from gozar.db.repositories.site_landing_page import SiteLandingPageRepository
from gozar.web.dependencies import DbSession

router = APIRouter(tags=["public"])

_LOCALES = {"fa", "en"}


class PageSummary(BaseModel):
    """List item — deliberately WITHOUT ``body`` so the sitemap/index reads stay light."""

    slug: str
    locale: str
    title: str
    meta_description: str
    location_remark: str | None
    updated_at: datetime | None


class PageOut(PageSummary):
    heading: str | None
    body: str  # trusted admin-authored HTML markup (see admin/landing.py) — rendered by the site


def _require_locale(locale: str) -> None:
    if locale not in _LOCALES:
        raise HTTPException(422, "locale must be 'fa' or 'en'")  # same idiom as admin/landing.py


def _summary(page: SiteLandingPage) -> PageSummary:
    return PageSummary(
        slug=page.slug,
        locale=page.locale,
        title=page.title,
        meta_description=page.meta_description,
        location_remark=page.location_remark,
        updated_at=page.updated_at,
    )


@router.get("/pages", response_model=list[PageSummary])
async def list_pages(
    session: DbSession, locale: str | None = Query(default=None)
) -> list[PageSummary]:
    """Published landings (optionally one locale) — feeds the sitemap and the locations index."""
    if locale is not None:
        _require_locale(locale)
    rows = await SiteLandingPageRepository(session).list_published(locale)
    return [_summary(p) for p in rows]


@router.get("/pages/{slug}", response_model=PageOut)
async def get_page(slug: str, session: DbSession, locale: str = Query(default="fa")) -> PageOut:
    """One published landing by slug, with a fa fallback when the requested locale has no row.

    The site serves both locales on a single URL (cookie-switched), so a missing/unpublished en row
    falls back to the fa one in this same request — the response's ``locale`` field carries the
    locale actually served so the renderer can set the article's ``lang``/``dir``.
    """
    _require_locale(locale)
    repo = SiteLandingPageRepository(session)
    page = await repo.get_by_slug(slug, locale)
    if (page is None or not page.published) and locale != "fa":
        page = await repo.get_by_slug(slug, "fa")
    if page is None or not page.published:  # get_by_slug is unpublished-agnostic — check here
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "page not found")
    return PageOut(**_summary(page).model_dump(), heading=page.heading, body=page.body)
