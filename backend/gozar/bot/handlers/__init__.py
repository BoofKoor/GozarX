"""Bot routers, included in dispatch order."""

from aiogram import Dispatcher

from gozar.bot.handlers import admin, config, invite, menu, settings, start, status


def register_handlers(dp: Dispatcher) -> None:
    # `admin` is registered right after `start` and is owner-gated (IsOwner), so its FSM message
    # handlers claim an owner's mid-flow messages before the feature routers see them; a non-owner's
    # update never matches it and falls through. Feature routers come before `menu` (home + help).
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(config.router)
    dp.include_router(status.router)
    dp.include_router(invite.router)
    dp.include_router(settings.router)
    dp.include_router(menu.router)
