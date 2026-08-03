"""Website SEO landing pages (auth-gated) — CRUD over ``site_landing_pages``.

The flat ``content`` table can't carry a slug + SEO meta, so landings get their own table (one row
per slug+locale, fa/en only). The public site later renders the ``published`` rows by slug. ``body``
is trusted admin-authored markup; user-facing rendering must still treat it consciously (documented
where the public site consumes it) — nothing here is user-supplied.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from gozar.db.models.site_landing_page import SiteLandingPage
from gozar.db.repositories.site_landing_page import SiteLandingPageRepository
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/site/pages", tags=["site-pages"])

_LOCALES = {"fa", "en"}


class LandingOut(BaseModel):
    id: int
    slug: str
    locale: str
    title: str
    meta_description: str
    heading: str | None
    body: str
    location_remark: str | None
    published: bool
    created_at: datetime | None
    updated_at: datetime | None


class LandingIn(BaseModel):
    slug: str = Field(min_length=1, max_length=128)
    locale: str
    title: str = Field(min_length=1, max_length=200)
    meta_description: str = Field(default="", max_length=320)
    heading: str | None = Field(default=None, max_length=200)
    body: str = ""
    location_remark: str | None = Field(default=None, max_length=128)
    published: bool = True


def _out(p: SiteLandingPage) -> LandingOut:
    return LandingOut(
        id=p.id,
        slug=p.slug,
        locale=p.locale,
        title=p.title,
        meta_description=p.meta_description,
        heading=p.heading,
        body=p.body,
        location_remark=p.location_remark,
        published=p.published,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _require_locale(locale: str) -> None:
    if locale not in _LOCALES:
        raise HTTPException(422, "locale must be 'fa' or 'en'")


@router.get("/", response_model=list[LandingOut])
async def list_pages(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    locale: str | None = Query(None),
) -> list[LandingOut]:
    rows = await SiteLandingPageRepository(session).list(locale)
    return [_out(p) for p in rows]


@router.post("/", response_model=LandingOut, status_code=status.HTTP_201_CREATED)
async def create_page(
    body: LandingIn, request: Request, session: DbSession, admin: AdminUser
) -> LandingOut:
    _require_locale(body.locale)
    repo = SiteLandingPageRepository(session)
    if await repo.get_by_slug(body.slug, body.locale) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "a page with this slug+locale already exists")
    try:
        page = await repo.create(
            slug=body.slug,
            locale=body.locale,
            title=body.title,
            meta_description=body.meta_description,
            heading=body.heading,
            body=body.body,
            location_remark=body.location_remark,
            published=body.published,
        )
    except IntegrityError as exc:  # a concurrent create won the (slug, locale) race
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a page with this slug+locale already exists"
        ) from exc
    return _out(page)


@router.get("/{page_id}", response_model=LandingOut)
async def get_page(
    page_id: int, request: Request, session: DbSession, admin: AdminUser
) -> LandingOut:
    page = await SiteLandingPageRepository(session).get(page_id)
    if page is None:
        raise HTTPException(404, "page not found")
    return _out(page)


@router.put("/{page_id}", response_model=LandingOut)
async def update_page(
    page_id: int, body: LandingIn, request: Request, session: DbSession, admin: AdminUser
) -> LandingOut:
    _require_locale(body.locale)
    repo = SiteLandingPageRepository(session)
    page = await repo.get(page_id)
    if page is None:
        raise HTTPException(404, "page not found")
    clash = await repo.get_by_slug(body.slug, body.locale)
    if clash is not None and clash.id != page_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "a page with this slug+locale already exists")
    try:
        page = await repo.update(
            page,
            slug=body.slug,
            locale=body.locale,
            title=body.title,
            meta_description=body.meta_description,
            heading=body.heading,
            body=body.body,
            location_remark=body.location_remark,
            published=body.published,
        )
    except IntegrityError as exc:  # a concurrent write took (slug, locale) between check and flush
        raise HTTPException(
            status.HTTP_409_CONFLICT, "a page with this slug+locale already exists"
        ) from exc
    return _out(page)


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(page_id: int, request: Request, session: DbSession, admin: AdminUser) -> None:
    repo = SiteLandingPageRepository(session)
    page = await repo.get(page_id)
    if page is None:
        raise HTTPException(404, "page not found")
    await repo.delete(page)
