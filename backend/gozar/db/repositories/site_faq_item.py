"""Site FAQ repository — CRUD over ``site_faq_items`` (the public site's questions).

Follows the base contract: ``flush``, never ``commit``. Ordering is always ``(position, id)`` so two
items sharing a position keep a stable, deterministic order instead of shuffling between requests.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from gozar.db.models.site_faq_item import SiteFaqItem
from gozar.db.repositories.base import BaseRepository


class SiteFaqItemRepository(BaseRepository):
    async def list(self, locale: str | None = None) -> list[SiteFaqItem]:
        """Every item (optionally one locale), published or not — the admin list."""
        stmt = select(SiteFaqItem)
        if locale is not None:
            stmt = stmt.where(SiteFaqItem.locale == locale)
        rows = await self.session.scalars(
            stmt.order_by(SiteFaqItem.locale, SiteFaqItem.position, SiteFaqItem.id)
        )
        return list(rows.all())

    async def list_published(self, locale: str) -> list[SiteFaqItem]:
        """Published items for one locale — the public site's read path."""
        rows = await self.session.scalars(
            select(SiteFaqItem)
            .where(SiteFaqItem.locale == locale, SiteFaqItem.published.is_(True))
            .order_by(SiteFaqItem.position, SiteFaqItem.id)
        )
        return list(rows.all())

    async def get(self, id_: int) -> SiteFaqItem | None:
        return await self.session.get(SiteFaqItem, id_)

    async def get_by_question(self, locale: str, question: str) -> SiteFaqItem | None:
        """The (locale, question) unique lookup — guards create/edit against a duplicate."""
        return await self.session.scalar(
            select(SiteFaqItem).where(
                SiteFaqItem.locale == locale, SiteFaqItem.question == question
            )
        )

    async def next_position(self, locale: str) -> int:
        """One past the locale's highest position, so a new item lands at the END of the list.

        Defaulting to 0 instead would insert every new question at the top, silently reordering a
        list the operator had already arranged.
        """
        highest = await self.session.scalar(
            select(func.max(SiteFaqItem.position)).where(SiteFaqItem.locale == locale)
        )
        return int(highest) + 1 if highest is not None else 0

    async def create(
        self,
        *,
        locale: str,
        category: str,
        question: str,
        answer: str,
        position: int | None = None,
        published: bool = True,
    ) -> SiteFaqItem:
        item = SiteFaqItem(
            locale=locale,
            category=category,
            question=question,
            answer=answer,
            position=position if position is not None else await self.next_position(locale),
            published=published,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def update(
        self,
        item: SiteFaqItem,
        *,
        locale: str,
        category: str,
        question: str,
        answer: str,
        position: int,
        published: bool,
    ) -> SiteFaqItem:
        item.locale = locale
        item.category = category
        item.question = question
        item.answer = answer
        item.position = position
        item.published = published
        await self.session.flush()
        return item

    async def reorder(self, ids: list[int]) -> int:
        """Apply an explicit order: item at index ``i`` of ``ids`` gets ``position = i``.

        Reordering by editing one row at a time can't express "move this to the top" without N
        writes and a transient state where two items claim the same slot. Returns how many of the
        requested ids actually existed, so the caller can reject a stale list rather than silently
        applying a partial order.
        """
        if not ids:
            return 0
        rows = await self.session.scalars(select(SiteFaqItem).where(SiteFaqItem.id.in_(ids)))
        by_id = {item.id: item for item in rows.all()}
        for index, id_ in enumerate(ids):
            item = by_id.get(id_)
            if item is not None:
                item.position = index
        await self.session.flush()
        return len(by_id)

    async def delete(self, item: SiteFaqItem) -> None:
        await self.session.delete(item)
        await self.session.flush()

    async def add_default(
        self,
        *,
        locale: str,
        category: str,
        question: str,
        answer: str,
        position: int,
        published: bool = True,
    ) -> None:
        """Insert a seed item only if (locale, question) is absent — never clobbers admin edits.

        Same per-row idempotency as ``SiteLandingPageRepository.add_default``: the boot-time seeder
        runs on every start, and an item the operator reworded or unpublished stays as they left it.
        """
        stmt = pg_insert(SiteFaqItem).values(
            locale=locale,
            category=category,
            question=question,
            answer=answer,
            position=position,
            published=published,
        )
        await self.session.execute(
            stmt.on_conflict_do_nothing(
                index_elements=[SiteFaqItem.locale, SiteFaqItem.question],
            )
        )
