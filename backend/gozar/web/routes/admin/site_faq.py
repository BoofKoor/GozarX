"""Website FAQ (auth-gated) — CRUD + reordering over ``site_faq_items``.

The site's FAQ was 16 strings compiled into its bundle: every new recurring question cost a code
change and a redeploy. These rows carry the same shape the site already renders, so answering a
support question is now a panel edit.

``question``/``answer`` are PLAIN TEXT, deliberately — unlike the landing pages' ``body`` there is
no HTML here, and the site renders them as text. Keeping it that way means an FAQ answer can never
become a script tag on either the public site or the panel that previews it.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from gozar.db.models.site_faq_item import FAQ_CATEGORIES, SiteFaqItem
from gozar.db.repositories.site_faq_item import SiteFaqItemRepository
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/site/faq", tags=["site-faq"])

_LOCALES = {"fa", "en"}
_DUPLICATE = "this question already exists in that language"


class FaqOut(BaseModel):
    id: int
    locale: str
    category: str
    question: str
    answer: str
    position: int
    published: bool
    created_at: datetime | None
    updated_at: datetime | None


class FaqIn(BaseModel):
    locale: str
    category: str
    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1, max_length=4000)
    published: bool = True
    # Omitted on create → appended to the end of the locale's list (see repo.next_position). A new
    # question defaulting to 0 would jump to the top and reorder a list the operator arranged.
    position: int | None = Field(default=None, ge=0)


class ReorderIn(BaseModel):
    """The locale's item ids in their new display order (index becomes ``position``)."""

    ids: list[int] = Field(min_length=1)


def _out(item: SiteFaqItem) -> FaqOut:
    return FaqOut(
        id=item.id,
        locale=item.locale,
        category=item.category,
        question=item.question,
        answer=item.answer,
        position=item.position,
        published=item.published,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _validate(body: FaqIn) -> None:
    if body.locale not in _LOCALES:
        raise HTTPException(422, "locale must be 'fa' or 'en'")
    if body.category not in FAQ_CATEGORIES:
        # An unknown category isn't cosmetic: the site's tabs are built from this fixed set, so the
        # item would only ever appear under "all" and look like it vanished from its section.
        raise HTTPException(422, f"category must be one of: {', '.join(FAQ_CATEGORIES)}")


@router.get("/", response_model=list[FaqOut])
async def list_faq(
    request: Request,
    session: DbSession,
    admin: AdminUser,
    locale: str | None = Query(None),
) -> list[FaqOut]:
    rows = await SiteFaqItemRepository(session).list(locale)
    return [_out(i) for i in rows]


@router.post("/", response_model=FaqOut, status_code=status.HTTP_201_CREATED)
async def create_faq(body: FaqIn, request: Request, session: DbSession, admin: AdminUser) -> FaqOut:
    _validate(body)
    repo = SiteFaqItemRepository(session)
    if await repo.get_by_question(body.locale, body.question) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE)
    try:
        item = await repo.create(
            locale=body.locale,
            category=body.category,
            question=body.question,
            answer=body.answer,
            position=body.position,
            published=body.published,
        )
    except IntegrityError as exc:  # a concurrent create won the (locale, question) race
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE) from exc
    return _out(item)


@router.put("/reorder", response_model=list[FaqOut])
async def reorder_faq(
    body: ReorderIn, request: Request, session: DbSession, admin: AdminUser
) -> list[FaqOut]:
    """Apply an explicit order in one write, instead of N single-row position edits."""
    repo = SiteFaqItemRepository(session)
    applied = await repo.reorder(body.ids)
    if applied != len(body.ids):
        # The page is working from a stale list (something was deleted elsewhere). Applying the
        # partial order anyway would silently reshuffle the items that DO exist.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "some items no longer exist — reload the list and try again"
        )
    return [_out(i) for i in await repo.list()]


@router.put("/{item_id}", response_model=FaqOut)
async def update_faq(
    item_id: int, body: FaqIn, request: Request, session: DbSession, admin: AdminUser
) -> FaqOut:
    _validate(body)
    repo = SiteFaqItemRepository(session)
    item = await repo.get(item_id)
    if item is None:
        raise HTTPException(404, "faq item not found")
    clash = await repo.get_by_question(body.locale, body.question)
    if clash is not None and clash.id != item_id:
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE)
    try:
        item = await repo.update(
            item,
            locale=body.locale,
            category=body.category,
            question=body.question,
            answer=body.answer,
            position=body.position if body.position is not None else item.position,
            published=body.published,
        )
    except IntegrityError as exc:  # a concurrent write took (locale, question) after the check
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE) from exc
    return _out(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq(item_id: int, request: Request, session: DbSession, admin: AdminUser) -> None:
    repo = SiteFaqItemRepository(session)
    item = await repo.get(item_id)
    if item is None:
        raise HTTPException(404, "faq item not found")
    await repo.delete(item)
