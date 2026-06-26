"""User repository."""

from __future__ import annotations

from sqlalchemy import func, select

from gozar.db.models.enums import Language
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
