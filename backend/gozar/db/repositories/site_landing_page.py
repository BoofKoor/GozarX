"""Site landing-page repository — CRUD for the admin 'website' SEO landings (P9).

One row per (slug, locale). The admin section manages these; the public site later reads the
``published`` rows by slug. Follows the base contract: ``flush``, never ``commit``.
"""

from __future__ import annotations

from sqlalchemy import select

from gozar.db.models.site_landing_page import SiteLandingPage
from gozar.db.repositories.base import BaseRepository


class SiteLandingPageRepository(BaseRepository):
    async def list(self, locale: str | None = None) -> list[SiteLandingPage]:
        """All landing rows (optionally one locale), ordered by slug then locale — admin list."""
        stmt = select(SiteLandingPage)
        if locale is not None:
            stmt = stmt.where(SiteLandingPage.locale == locale)
        stmt = stmt.order_by(SiteLandingPage.slug, SiteLandingPage.locale)
        rows = await self.session.scalars(stmt)
        return list(rows.all())

    async def list_published(self, locale: str | None = None) -> list[SiteLandingPage]:
        """Published rows only — the public site's read path (SEO landings)."""
        stmt = select(SiteLandingPage).where(SiteLandingPage.published.is_(True))
        if locale is not None:
            stmt = stmt.where(SiteLandingPage.locale == locale)
        # (slug, locale) is the unique key — order by both for a stable, deterministic result when
        # two locales share a slug (ordering by slug alone leaves their relative order undefined).
        rows = await self.session.scalars(
            stmt.order_by(SiteLandingPage.slug, SiteLandingPage.locale)
        )
        return list(rows.all())

    async def get(self, id_: int) -> SiteLandingPage | None:
        return await self.session.get(SiteLandingPage, id_)

    async def get_by_slug(self, slug: str, locale: str) -> SiteLandingPage | None:
        """The (slug, locale) unique lookup — used to render a landing and to guard create/edit."""
        return await self.session.scalar(
            select(SiteLandingPage).where(
                SiteLandingPage.slug == slug, SiteLandingPage.locale == locale
            )
        )

    async def create(
        self,
        *,
        slug: str,
        locale: str,
        title: str,
        meta_description: str = "",
        heading: str | None = None,
        body: str = "",
        location_remark: str | None = None,
        published: bool = True,
    ) -> SiteLandingPage:
        page = SiteLandingPage(
            slug=slug,
            locale=locale,
            title=title,
            meta_description=meta_description,
            heading=heading,
            body=body,
            location_remark=location_remark,
            published=published,
        )
        self.session.add(page)
        await self.session.flush()
        return page

    async def update(
        self,
        page: SiteLandingPage,
        *,
        slug: str,
        locale: str,
        title: str,
        meta_description: str,
        heading: str | None,
        body: str,
        location_remark: str | None,
        published: bool,
    ) -> SiteLandingPage:
        page.slug = slug
        page.locale = locale
        page.title = title
        page.meta_description = meta_description
        page.heading = heading
        page.body = body
        page.location_remark = location_remark
        page.published = published
        await self.session.flush()
        return page

    async def delete(self, page: SiteLandingPage) -> None:
        await self.session.delete(page)
        await self.session.flush()
