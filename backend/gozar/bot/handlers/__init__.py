"""Bot routers, included in dispatch order."""

from aiogram import Dispatcher

from gozar.bot.handlers import menu, start


def register_handlers(dp: Dispatcher) -> None:
    # Phases 4-5 insert their feature routers BEFORE `menu` so their menu:* handlers take precedence
    # over the placeholder.
    dp.include_router(start.router)
    dp.include_router(menu.router)
