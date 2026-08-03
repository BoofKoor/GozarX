"""User repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, cast, delete, func, or_, select
from sqlalchemy.sql import Select

from gozar.config.reporting import DISPLAY_TZ_NAME
from gozar.db.models.config_log import ConfigLog
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.base import BaseRepository


def _filtered(stmt: Select, status: UserStatus | None, search: str | None) -> Select:
    """Apply the admin user-list filters: optional status + a substring search over telegram_id
    (matched as text) or panel_username. Shared by the page query and its count."""
    if status is not None:
        stmt = stmt.where(User.status == status)
    if search and search.strip():
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(cast(User.telegram_id, String).ilike(like), User.panel_username.ilike(like))
        )
    return stmt


class UserRepository(BaseRepository):
    async def get(self, telegram_id: int) -> User | None:
        return await self.session.get(User, telegram_id)

    async def get_by_panel_username(self, panel_username: str) -> User | None:
        """Reverse lookup for the panel webhook: map a Remnawave username back to its Gozar user."""
        return await self.session.scalar(select(User).where(User.panel_username == panel_username))

    async def create(
        self,
        telegram_id: int,
        *,
        language: Language | None = None,
        referred_by: int | None = None,
    ) -> User:
        user = User(telegram_id=telegram_id, referred_by=referred_by)
        if language is not None:
            user.language = language
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_or_create(
        self,
        telegram_id: int,
        *,
        language: Language | None = None,
        referred_by: int | None = None,
    ) -> tuple[User, bool]:
        """Return (user, created). ``created`` is True only when a new row was inserted."""
        user = await self.get(telegram_id)
        if user is not None:
            return user, False
        return await self.create(telegram_id, language=language, referred_by=referred_by), True

    async def count(self) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(User)) or 0)

    async def count_by_status(self, status: UserStatus) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).select_from(User).where(User.status == status)
            )
            or 0
        )

    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        status: UserStatus | None = None,
        search: str | None = None,
    ) -> list[User]:
        """A page of users (newest first) for the admin panel, with optional status + search."""
        stmt = _filtered(select(User), status, search)
        # telegram_id (PK) tiebreak: created_at can tie for users who ran /start in the same second,
        # and without a unique tiebreak LIMIT/OFFSET paging would drop/duplicate them across pages.
        stmt = stmt.order_by(User.created_at.desc(), User.telegram_id.desc())
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def count_filtered(
        self, *, status: UserStatus | None = None, search: str | None = None
    ) -> int:
        """Total rows matching the same status + search filter — drives the page count."""
        stmt = _filtered(select(func.count()).select_from(User), status, search)
        return int(await self.session.scalar(stmt) or 0)

    async def count_created_since(self, since: datetime) -> int:
        """Users registered at/after ``since`` — backs the new-today / new-this-week KPIs."""
        return int(
            await self.session.scalar(
                select(func.count()).select_from(User).where(User.created_at >= since)
            )
            or 0
        )

    async def count_reminder_enabled(self) -> int:
        """How many users keep reminders on (engagement signal)."""
        return int(
            await self.session.scalar(
                select(func.count()).select_from(User).where(User.reminder_enabled.is_(True))
            )
            or 0
        )

    async def sum_referrals(self) -> int:
        """Total referrals across all users (one number for the admin stats screen)."""
        return int(
            await self.session.scalar(select(func.coalesce(func.sum(User.referral_count), 0))) or 0
        )

    async def language_breakdown(self) -> list[tuple[str, int]]:
        """Users grouped by language → ``[(lang_value, count), …]`` most-common first.
        Backs the dashboard language donut."""
        count = func.count().label("n")
        rows = await self.session.execute(
            select(User.language, count).group_by(User.language).order_by(count.desc())
        )
        return [(getattr(lang, "value", lang), int(n)) for lang, n in rows.all()]

    async def top_referrers(self, limit: int = 5) -> list[tuple[int, int]]:
        """The biggest inviters (referral_count > 0) → ``[(telegram_id, count), …]`` desc."""
        rows = await self.session.execute(
            select(User.telegram_id, User.referral_count)
            .where(User.referral_count > 0)
            .order_by(User.referral_count.desc())
            .limit(limit)
        )
        return [(int(tid), int(n)) for tid, n in rows.all()]

    async def signups_daily(self, since: datetime) -> list[tuple[str, int]]:
        """Signups per LOCAL day at/after ``since`` → ``[(YYYY-MM-DD, count), …]`` ascending.
        Mirrors ConfigLogRepository.daily_counts for the dashboard growth chart."""
        # Bucketed on the LOCAL calendar day (DISPLAY_TZ), not the UTC one: the operator reads
        # these on Iran time, so a UTC bucket split every one of their days 3.5 hours early.
        day = func.date(func.timezone(DISPLAY_TZ_NAME, User.created_at)).label("day")
        rows = await self.session.execute(
            select(day, func.count()).where(User.created_at >= since).group_by(day).order_by(day)
        )
        return [(d.isoformat(), int(n)) for d, n in rows.all()]

    async def list_all_ids(self) -> list[int]:
        """Every telegram_id — the broadcast/forward audience. Materialised once so the worker can
        throttle its fan-out without holding a DB cursor open for the whole (minutes-long) send."""
        result = await self.session.scalars(select(User.telegram_id))
        return list(result.all())

    async def list_ids_by_languages(self, langs: list[Language]) -> list[int]:
        """telegram_ids of users whose language is in ``langs`` (empty ⇒ all) — the language-
        targeted broadcast audience. Materialised once, like ``list_all_ids``."""
        stmt = select(User.telegram_id)
        if langs:
            stmt = stmt.where(User.language.in_(langs))
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def count_by_languages(self, langs: list[Language]) -> int:
        """Recipient count for a language-targeted broadcast (empty ⇒ all)."""
        stmt = select(func.count()).select_from(User)
        if langs:
            stmt = stmt.where(User.language.in_(langs))
        return int(await self.session.scalar(stmt) or 0)

    async def list_panel_usernames_by_status(self, status: UserStatus) -> list[str]:
        """Live panel usernames of users in a status (non-null) — backs the bulk traffic reset."""
        result = await self.session.scalars(
            select(User.panel_username).where(
                User.status == status, User.panel_username.is_not(None)
            )
        )
        return [name for name in result.all() if name]

    async def list_active_with_panel(self) -> list[tuple[int, str]]:
        """``(telegram_id, panel_username)`` for every ``active_config`` user with a live panel
        account — the audience the ``reconcile_trials`` sweep probes for ended/limited trials."""
        rows = await self.session.execute(
            select(User.telegram_id, User.panel_username).where(
                User.status == UserStatus.active_config, User.panel_username.is_not(None)
            )
        )
        return [(int(tid), name) for tid, name in rows.all() if name]

    async def delete(self, telegram_id: int) -> None:
        """Remove a user row (a broadcast removes a user ONLY on a genuine blocked/deactivated send
        error — never on a transient failure). ``config_logs`` cascade-delete via the FK."""
        await self.session.execute(delete(User).where(User.telegram_id == telegram_id))

    # --- analytics (Phase B) ---------------------------------------------------------------------
    async def referral_funnel(self) -> tuple[int, int]:
        """``(joined_via_referral, of_those_who_claimed)`` — the invitee side of the referral funnel
        (``referred_by`` was indexed but unused in stats). Lets the panel show invitee conversion
        and a viral proxy, not just the top-referrer leaderboard."""
        joined = int(
            await self.session.scalar(
                select(func.count()).select_from(User).where(User.referred_by.is_not(None))
            )
            or 0
        )
        claimed = int(
            await self.session.scalar(
                select(func.count(func.distinct(User.telegram_id)))
                .select_from(User)
                .join(ConfigLog, ConfigLog.user_id == User.telegram_id)
                .where(User.referred_by.is_not(None))
            )
            or 0
        )
        return joined, claimed

    async def reminder_by_language(self) -> list[tuple[str, int, int]]:
        """Per language → ``[(lang, reminders_on, reminders_off), …]`` — the opt-in engagement
        signal broken out by cohort instead of one global number."""
        on = func.count().filter(User.reminder_enabled.is_(True))
        off = func.count().filter(User.reminder_enabled.is_(False))
        rows = await self.session.execute(select(User.language, on, off).group_by(User.language))
        return [(getattr(lang, "value", lang), int(a), int(b)) for lang, a, b in rows.all()]

    # --- period comparison + deeper analytics ----------------------------------------------------
    async def count_created_between(self, start: datetime, end: datetime) -> int:
        """Signups in the half-open window ``[start, end)``. Backs the "vs the previous period"
        deltas: the same figure is asked for this window and the one immediately before it, so the
        two are always the same length and the comparison is honest."""
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.created_at >= start, User.created_at < end)
            )
            or 0
        )

    async def signups_hourly_weekday(
        self, since: datetime, tz: str = DISPLAY_TZ_NAME
    ) -> list[tuple[int, int, int]]:
        """Signups bucketed by (weekday, hour) in ``tz`` local time → ``[(dow, hour, count), …]``.
        The signup twin of ``ConfigLogRepository.hourly_weekday_counts``: when people ARRIVE is a
        different question from when they claim, and only the second one was ever charted."""
        local = func.timezone(tz, User.created_at)
        dow = func.extract("dow", local).label("dow")
        hour = func.extract("hour", local).label("hour")
        rows = await self.session.execute(
            select(dow, hour, func.count()).where(User.created_at >= since).group_by(dow, hour)
        )
        return [(int(d), int(h), int(n)) for d, h, n in rows.all()]

    async def referral_cap_stats(self, cap: int) -> tuple[int, int]:
        """``(at_cap, any_referrals)`` for the configured reward cap — how many inviters have
        hit the ceiling and stopped earning. A cap of 0 means "no cap configured", so nobody is
        at it."""
        any_referrals = int(
            await self.session.scalar(
                select(func.count()).select_from(User).where(User.referral_count > 0)
            )
            or 0
        )
        if cap <= 0:
            return 0, any_referrals
        at_cap = int(
            await self.session.scalar(
                select(func.count()).select_from(User).where(User.referral_count >= cap)
            )
            or 0
        )
        return at_cap, any_referrals

    async def status_breakdown(self) -> list[tuple[str, int]]:
        """Users grouped by status → ``[(status_value, count), …]``. One grouped query in place of
        the three separate ``count_by_status`` calls the stats screen used to make."""
        rows = await self.session.execute(select(User.status, func.count()).group_by(User.status))
        return [(getattr(s, "value", s), int(n)) for s, n in rows.all()]
