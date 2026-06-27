"""User repository."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.db.repositories.base import BaseRepository


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

    async def sum_referrals(self) -> int:
        """Total referrals across all users (one number for the admin stats screen)."""
        return int(
            await self.session.scalar(select(func.coalesce(func.sum(User.referral_count), 0))) or 0
        )

    async def list_all_ids(self) -> list[int]:
        """Every telegram_id — the broadcast/forward audience. Materialised once so the worker can
        throttle its fan-out without holding a DB cursor open for the whole (minutes-long) send."""
        result = await self.session.scalars(select(User.telegram_id))
        return list(result.all())

    async def list_panel_usernames_by_status(self, status: UserStatus) -> list[str]:
        """Live panel usernames of users in a status (non-null) — backs the bulk traffic reset."""
        result = await self.session.scalars(
            select(User.panel_username).where(
                User.status == status, User.panel_username.is_not(None)
            )
        )
        return [name for name in result.all() if name]

    async def delete(self, telegram_id: int) -> None:
        """Remove a user row (a broadcast removes a user ONLY on a genuine blocked/deactivated send
        error — never on a transient failure). ``config_logs`` cascade-delete via the FK."""
        await self.session.execute(delete(User).where(User.telegram_id == telegram_id))
