"""Bot routers, included in dispatch order."""

from aiogram import Dispatcher

from gozar.bot.handlers import config, invite, menu, settings, start, status


def register_handlers(dp: Dispatcher) -> None:
    # Feature routers are included BEFORE `menu`; with config/status/invite/settings all live now,
    # `menu` owns only home + help (no placeholders left).
    dp.include_router(start.router)
    dp.include_router(config.router)
    dp.include_router(status.router)
    dp.include_router(invite.router)
    dp.include_router(settings.router)
    dp.include_router(menu.router)
