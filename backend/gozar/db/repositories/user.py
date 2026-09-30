"""User repository."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import String, cast, delete, func, or_, select, update
from sqlalchemy.sql import Select

from gozar.config.reporting import DISPLAY_TZ_NAME
from gozar.db.models.config_log import ConfigLog
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.base import LIKE_ESCAPE, BaseRepository, contains_pattern

#: Ids per ``mark_unreachable`` statement — far under asyncpg's 32,767 bind-parameter ceiling.
MARK_BATCH = 5_000


def _latest_claim_location():  # a correlated scalar subquery
    """The location of THIS user's most recent claim, as a correlated scalar subquery.

    "Which location is this user on" is the latest claim, not any claim: a user who tried Germany
    once and has been on Finland ever since must not appear under Germany.

    Correlated (one ``LIMIT 1`` probe per user on ``ix_config_logs_user_created_id``) rather than
    a window function ranking every claim ever made: measured 0.37s against 0.92s on 1.3M claims,
    and the gap grows with the table while the per-user probe does not. ``id`` breaks the tie
    between two claims in the same microsecond, as ``ConfigLogRepository.latest_locations`` does.
    """
    return (
        select(ConfigLog.location)
        .where(ConfigLog.user_id == User.telegram_id)
        .order_by(ConfigLog.created_at.desc(), ConfigLog.id.desc())
        .limit(1)
        .correlate(User)
        .scalar_subquery()
    )


def _filtered(
    stmt: Select, status: UserStatus | None, search: str | None, location: str | None = None
) -> Select:
    """Apply the admin user-list filters: optional status, a substring search over telegram_id
    (matched as text) or panel_username, and the user's current location. Shared by the page query,
    its count and the CSV export, so the three can never disagree about what "matching" means."""
    if status is not None:
        stmt = stmt.where(User.status == status)
    if search and search.strip():
        like = contains_pattern(search.strip())
        stmt = stmt.where(
            or_(
                cast(User.telegram_id, String).ilike(like, escape=LIKE_ESCAPE),
                User.panel_username.ilike(like, escape=LIKE_ESCAPE),
            )
        )
    if location and location.strip():
        stmt = stmt.where(_latest_claim_location() == location.strip())
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
        location: str | None = None,
    ) -> list[User]:
        """A page of users (newest first), with optional status / search / location filters."""
        stmt = _filtered(select(User), status, search, location)
        # telegram_id (PK) tiebreak: created_at can tie for users who ran /start in the same second,
        # and without a unique tiebreak LIMIT/OFFSET paging would drop/duplicate them across pages.
        stmt = stmt.order_by(User.created_at.desc(), User.telegram_id.desc())
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.scalars(stmt)
        return list(result.all())

    @staticmethod
    def export_statement(
        *,
        status: UserStatus | None = None,
        search: str | None = None,
        location: str | None = None,
    ) -> Select:
        """The export's rows (user columns + latest location + lifetime claims), filtered like the
        page.

        One statement with both extras as correlated subqueries (index probes on
        ``config_logs (user_id, created_at, id)``) — so the export needs no second query keyed by a
        list of ids, which is what broke it past 32,767 users.
        """
        claims = (
            select(func.count())
            .select_from(ConfigLog)
            .where(ConfigLog.user_id == User.telegram_id)
            .correlate(User)
            .scalar_subquery()
        )
        # Plain columns, not ORM entities: at 100k+ rows the identity map was most of the cost.
        stmt = select(
            User.telegram_id,
            User.status,
            User.language,
            User.referral_count,
            User.panel_username,
            _latest_claim_location().label("location"),
            claims.label("claims"),
            User.last_claim_at,
            User.created_at,
        )
        stmt = _filtered(stmt, status, search, location)
        return stmt.order_by(User.created_at.desc(), User.telegram_id.desc())

    async def count_filtered(
        self,
        *,
        status: UserStatus | None = None,
        search: str | None = None,
        location: str | None = None,
    ) -> int:
        """Total rows matching the same filter — drives the page count."""
        stmt = _filtered(select(func.count()).select_from(User), status, search, location)
        return int(await self.session.scalar(stmt) or 0)

    async def summary(
        self, **signups_since: datetime | tuple[datetime, datetime]
    ) -> dict[str, int]:
        """The dashboard's user-table headline from ONE scan: totals by status, referrals, reminder
        opt-ins, and a signup count per named window (a bound, or a half-open ``(start, end)``).

        These used to be eleven separate statements — three ``count_by_status`` calls, five
        ``count_created_since`` calls and three more — each its own pass over ``users``.
        """
        columns = [
            func.count(),
            func.count().filter(User.status == UserStatus.available),
            func.count().filter(User.status == UserStatus.active_config),
            func.count().filter(User.status == UserStatus.banned),
            func.coalesce(func.sum(User.referral_count), 0),
            func.count().filter(User.reminder_enabled.is_(True)),
        ]
        for bound in signups_since.values():
            if isinstance(bound, tuple):
                start, end = bound
                columns.append(func.count().filter(User.created_at >= start, User.created_at < end))
            else:
                columns.append(func.count().filter(User.created_at >= bound))
        row = (await self.session.execute(select(*columns).select_from(User))).one()
        keys = ("total", "available", "active", "banned", "referrals", "reminder_enabled")
        out = {key: int(value or 0) for key, value in zip(keys, row[: len(keys)], strict=True)}
        for name, value in zip(signups_since, row[len(keys) :], strict=True):
            out[name] = int(value or 0)
        return out

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
        """Every REACHABLE telegram_id — the broadcast/forward audience. Materialised once so the
        worker can throttle its fan-out without holding a DB cursor open for the whole send."""
        result = await self.session.scalars(
            select(User.telegram_id).where(User.unreachable_at.is_(None))
        )
        return list(result.all())

    async def mark_unreachable(self, telegram_ids: list[int], at: datetime) -> int:
        """Record that Telegram says these chats are gone. The rows — and their claim history —
        stay; the next update from any of them clears the mark (see the context middleware).

        Written in batches of ``MARK_BATCH``: an ``IN`` list binds one parameter per id, and asyncpg
        refuses a statement with more than 32,767 of them — so a broadcast that found 40,000 gone
        chats marked none of them, and failed its log row on the way out."""
        marked = 0
        for start in range(0, len(telegram_ids), MARK_BATCH):
            batch = telegram_ids[start : start + MARK_BATCH]
            result = await self.session.execute(
                update(User).where(User.telegram_id.in_(batch)).values(unreachable_at=at)
            )
            marked += int(result.rowcount or 0)
        return marked

    @staticmethod
    def _audience(
        stmt: Select,
        langs: list[Language] | None,
        only_active: bool,
        only_referrers: bool,
    ) -> Select:
        """The broadcast audience filter, shared by the id list and its count.

        One function so the number the operator reads before pressing send and the number of people
        the worker actually walks can never be computed differently. Banned users are excluded
        unconditionally: they cannot receive anything, and counting them would inflate every
        pre-flight figure the composer shows.
        """
        # Unreachable users too: Telegram has already said the chat is gone.
        stmt = stmt.where(User.status != UserStatus.banned, User.unreachable_at.is_(None))
        if langs:
            stmt = stmt.where(User.language.in_(langs))
        if only_active:
            stmt = stmt.where(User.status == UserStatus.active_config)
        if only_referrers:
            stmt = stmt.where(User.referral_count > 0)
        return stmt

    async def audience_ids(
        self,
        langs: list[Language] | None = None,
        *,
        only_active: bool = False,
        only_referrers: bool = False,
    ) -> list[int]:
        """telegram_ids of the broadcast audience. Materialised once, like ``list_all_ids``, so the
        worker can throttle a minutes-long fan-out without holding a cursor open."""
        stmt = self._audience(select(User.telegram_id), langs, only_active, only_referrers)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def count_audience(
        self,
        langs: list[Language] | None = None,
        *,
        only_active: bool = False,
        only_referrers: bool = False,
    ) -> int:
        """How many that audience contains — what the composer shows before sending."""
        stmt = self._audience(
            select(func.count()).select_from(User), langs, only_active, only_referrers
        )
        return int(await self.session.scalar(stmt) or 0)

    async def list_ids_by_languages(self, langs: list[Language]) -> list[int]:
        """telegram_ids of users whose language is in ``langs`` (empty ⇒ all) — the language-
        targeted broadcast audience. Materialised once, like ``list_all_ids``."""
        stmt = select(User.telegram_id).where(User.unreachable_at.is_(None))
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

    async def list_revoke_pending(self) -> list[tuple[int, str]]:
        """``(telegram_id, panel_username)`` for every BANNED user still holding a panel handle: the
        ban could not reach the panel, so the account still works until someone deletes it. The
        reconcile sweep does, and clears the handle once it is gone."""
        rows = await self.session.execute(
            select(User.telegram_id, User.panel_username).where(
                User.status == UserStatus.banned, User.panel_username.is_not(None)
            )
        )
        return [(int(tid), name) for tid, name in rows.all() if name]

    async def delete(self, telegram_id: int) -> None:
        """Remove a user row; ``config_logs`` cascade-delete via the FK. No broadcast calls this
        any more — a gone chat is MARKED (``mark_unreachable``), because the delete took the user's
        claim history and the only mapping back to their live panel account with it."""
        await self.session.execute(delete(User).where(User.telegram_id == telegram_id))

    # --- analytics (Phase B) ---------------------------------------------------------------------
    async def referral_funnel(self) -> tuple[int, int, int]:
        """``(joined_via_referral, of_those_who_claimed, could_have_been_referred)``.

        The third figure is the honest denominator for "what share of our users arrived via an
        invite". ``referred_by`` is written only on a brand-new ``/start`` carrying a referral
        payload, and the legacy import set it to NULL for every migrated row — so on a live install
        39,899 of 108,693 users predate the referral programme entirely and could never have had
        one. Dividing by all of them reported 10.8% where the real figure for the era in which
        referrals existed is 17.0%, and no amount of referral growth could move it much.

        The cutoff is the earliest signup that HAS a referrer, which needs no configuration and
        corrects itself: it is by definition the moment the programme started producing rows.
        """
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
        # Everyone who signed up at or after the first referral we ever recorded. With no referrals
        # at all the cutoff is NULL, the comparison matches nothing, and the count is 0 — which the
        # caller turns into a 0% share rather than a division by zero.
        cutoff = (
            select(func.min(User.created_at)).where(User.referred_by.is_not(None)).scalar_subquery()
        )
        eligible = int(
            await self.session.scalar(
                select(func.count()).select_from(User).where(User.created_at >= cutoff)
            )
            or 0
        )
        return joined, claimed, eligible

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
        hit the ceiling and stopped earning.

        A cap of 0 means NO invite is rewarded (the quota math everywhere is
        ``min(referrals, cap)``), so every inviter is already at it. It used to be reported as
        "no cap configured — unlimited", the opposite of what the bot actually did: an operator who
        set 0 for "no limit" had switched invite rewards off.
        """
        any_referrals = int(
            await self.session.scalar(
                select(func.count()).select_from(User).where(User.referral_count > 0)
            )
            or 0
        )
        if cap <= 0:
            return any_referrals, any_referrals
        at_cap = int(
            await self.session.scalar(
                select(func.count()).select_from(User).where(User.referral_count >= cap)
            )
            or 0
        )
        return at_cap, any_referrals

    async def active_config_split(self, trial_hours: int, *, now: datetime) -> tuple[int, int]:
        """``(live, stale)`` among users whose status is ``active_config``.

        The bot's twin of ``SiteDeviceRepository.active_config_split``. The status column is healed
        only by the panel webhook or the reconcile sweep, and the sweep skips a user whenever the
        panel does not answer — so the raw count kept dead trials in "active" for as long as the
        panel was down. "Live" is a trial whose window (``last_claim_at + trial_hours``) has not
        elapsed; a missing anchor is stale, since nothing says the trial is still running.
        """
        cutoff = now - timedelta(hours=max(trial_hours, 1))
        live = func.count().filter(User.last_claim_at > cutoff)
        stale = func.count().filter(or_(User.last_claim_at <= cutoff, User.last_claim_at.is_(None)))
        row = (
            await self.session.execute(
                select(live, stale).select_from(User).where(User.status == UserStatus.active_config)
            )
        ).one()
        return int(row[0] or 0), int(row[1] or 0)

    async def signup_conversion(
        self, **windows: tuple[datetime, datetime | None]
    ) -> dict[str, tuple[int, int]]:
        """``{name: (signed_up, claimed)}`` for each half-open signup window, in ONE scan.

        ``claimed`` counts the window's signups who have EVER taken a config. This is the windowed
        conversion the dashboard's radar needs: the old figure divided every claimer ever by every
        user ever, so it sat beside three windowed rates without moving when the range did.
        """
        claimed = select(ConfigLog.id).where(ConfigLog.user_id == User.telegram_id).exists()
        columns = []
        for start, end in windows.values():
            in_window = User.created_at >= start
            if end is not None:
                in_window = in_window & (User.created_at < end)
            columns.append(func.count().filter(in_window))
            columns.append(func.count().filter(in_window & claimed))
        earliest = min(start for start, _ in windows.values())
        row = (
            await self.session.execute(
                select(*columns).select_from(User).where(User.created_at >= earliest)
            )
        ).one()
        return {
            name: (int(row[2 * i] or 0), int(row[2 * i + 1] or 0)) for i, name in enumerate(windows)
        }

    async def status_breakdown(self) -> list[tuple[str, int]]:
        """Users grouped by status → ``[(status_value, count), …]``. One grouped query in place of
        the three separate ``count_by_status`` calls the stats screen used to make."""
        rows = await self.session.execute(select(User.status, func.count()).group_by(User.status))
        return [(getattr(s, "value", s), int(n)) for s, n in rows.all()]
