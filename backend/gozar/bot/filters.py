"""aiogram filters.

``IsOwner`` gates the whole admin router (applied to both ``router.message`` and
``router.callback_query``). Owners come from ``settings.owners`` (the ``OWNERS`` env var), read at
call time via ``get_settings()`` — never at import. A non-owner's update simply doesn't match any
admin handler and falls through, so the admin surface never leaks.
"""

from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import TelegramObject

from gozar.config.settings import get_settings


class IsOwner(Filter):
    async def __call__(self, event: TelegramObject) -> bool:
        tg_user = getattr(event, "from_user", None)
        return tg_user is not None and tg_user.id in get_settings().owners
