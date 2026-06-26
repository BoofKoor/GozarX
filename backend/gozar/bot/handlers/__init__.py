"""Bot routers, included in dispatch order."""

from aiogram import Dispatcher

from gozar.bot.handlers import config, menu, start, status


def register_handlers(dp: Dispatcher) -> None:
    # Feature routers are included BEFORE `menu` so their menu:* handlers take precedence over the
    # remaining placeholders (invite/settings arrive in Phase 5).
    dp.include_router(start.router)
    dp.include_router(config.router)
    dp.include_router(status.router)
    dp.include_router(menu.router)
