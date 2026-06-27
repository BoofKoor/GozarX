"""Seed default ``content`` + ``settings`` (idempotent, non-clobbering).

Run: ``python -m gozar.seed`` — the container entrypoint runs this after migrations on every boot.

Uses ``add_default`` (INSERT ... ON CONFLICT DO NOTHING), so it fills in defaults for MISSING keys only
and never overwrites values an admin has edited in the panel. The trial squad + locations are NOT seeded
(they are panel-specific and set in the first-run wizard).
"""

from __future__ import annotations

import asyncio
import logging

from gozar.config.logging import configure_logging
from gozar.config.settings import get_settings
from gozar.db.models.enums import Language
from gozar.db.repositories.content import ContentRepository
from gozar.db.repositories.settings import SettingsRepository
from gozar.db.session import create_engine, create_sessionmaker
from gozar.services.settings_service import SettingKey

logger = logging.getLogger("gozar.seed")

# Trial economics — editable from the panel. (trial squad + locations are wizard-only.)
DEFAULT_SETTINGS: dict[str, str] = {
    SettingKey.DAILY_LIMIT_MB: "1024",
    SettingKey.REFERRAL_REWARD_MB: "500",
    SettingKey.REFERRAL_REWARD_LIMIT: "10",
    SettingKey.TRIAL_HOURS: "24",
    SettingKey.ADS_ENABLED: "false",
}

# Core user-facing copy per language; placeholders are {token}. Button labels live in the in-code
# i18n map (Phase 3), NOT here.
DEFAULT_CONTENT: dict[str, dict[Language, str]] = {
    "welcome": {
        Language.fa: "به ربات خوش‌آمدید! 🌟\nهر روز یک کانفیگ آزمایشی رایگان بگیرید و با دعوت دوستان حجم روزانه‌تان را بیشتر کنید.",
        Language.en: "Welcome! 🌟\nGet one free trial config every day, and grow your daily allowance by inviting friends.",
        Language.ru: "Добро пожаловать! 🌟\nПолучайте бесплатный пробный конфиг каждый день и увеличивайте лимит, приглашая друзей.",
    },
    "help": {
        Language.fa: "راهنما:\n• «کانفیگ امروز» — دریافت کانفیگ آزمایشی روزانه\n• «دعوت دوستان» — افزایش حجم روزانه\n• «وضعیت من» — مصرف و زمان باقی‌مانده\n• «تنظیمات» — زبان و یادآوری‌ها",
        Language.en: 'Help:\n• "Today\'s config" — your daily trial config\n• "Invite friends" — grow your allowance\n• "My status" — usage and time left\n• "Settings" — language and reminders',
        Language.ru: "Помощь:\n• «Конфиг на сегодня» — пробный конфиг\n• «Пригласить друзей» — больше трафика\n• «Мой статус» — расход и остаток\n• «Настройки» — язык и напоминания",
    },
    "choose_language": {
        Language.fa: "لطفاً زبان خود را انتخاب کنید:",
        Language.en: "Please choose your language:",
        Language.ru: "Пожалуйста, выберите язык:",
    },
    "main_menu": {
        Language.fa: "از منوی زیر انتخاب کنید:",
        Language.en: "Choose from the menu below:",
        Language.ru: "Выберите из меню ниже:",
    },
    "choose_location": {
        Language.fa: "یک لوکیشن انتخاب کنید:",
        Language.en: "Pick a location:",
        Language.ru: "Выберите локацию:",
    },
    "config_size": {
        Language.fa: "🎁 حجم روزانهٔ شما: {size}\nبرای دریافت کانفیگ امروز، دکمهٔ زیر را بزنید.",
        Language.en: "🎁 Your daily allowance: {size}\nTap the button below to get today's config.",
        Language.ru: "🎁 Ваш дневной объём: {size}\nНажмите кнопку ниже, чтобы получить конфиг.",
    },
    "config_active": {
        Language.fa: "✅ کانفیگ شما فعال است.\n⏳ زمان باقی‌مانده: {remaining}\n📊 مصرف: {usage} از {total}",
        Language.en: "✅ Your config is active.\n⏳ Time left: {remaining}\n📊 Used: {usage} of {total}",
        Language.ru: "✅ Ваш конфиг активен.\n⏳ Осталось: {remaining}\n📊 Израсходовано: {usage} из {total}",
    },
    "config_delivered": {
        Language.fa: "کانفیگ شما برای «{location}» آماده است:\n\n<code>{link}</code>\n\n⏳ اعتبار تا: {expires}",
        Language.en: 'Your config for "{location}" is ready:\n\n<code>{link}</code>\n\n⏳ Valid until: {expires}',
        Language.ru: "Ваш конфиг для «{location}» готов:\n\n<code>{link}</code>\n\n⏳ Действует до: {expires}",
    },
    "already_claimed": {
        Language.fa: "شما امروز کانفیگ خود را گرفته‌اید. ✅\nفردا دوباره سر بزنید یا با دعوت دوستان حجم بگیرید.",
        Language.en: "You've already claimed today's config. ✅\nCome back tomorrow, or invite friends for more.",
        Language.ru: "Вы уже получили конфиг на сегодня. ✅\nЗаходите завтра или приглашайте друзей.",
    },
    "not_ready": {
        Language.fa: "🛠 ربات هنوز آمادهٔ ارائهٔ کانفیگ نیست.\nلطفاً کمی بعد دوباره تلاش کنید.",
        Language.en: "🛠 The bot isn't ready to hand out configs yet.\nPlease try again a little later.",
        Language.ru: "🛠 Бот ещё не готов выдавать конфиги.\nПожалуйста, попробуйте чуть позже.",
    },
    "no_locations": {
        Language.fa: "📍 در حال حاضر هیچ لوکیشنی در دسترس نیست.\nلطفاً بعداً دوباره سر بزنید.",
        Language.en: "📍 No locations are available right now.\nPlease check back later.",
        Language.ru: "📍 Сейчас нет доступных локаций.\nПожалуйста, загляните позже.",
    },
    "panel_error": {
        Language.fa: "⚠️ ارتباط با سرور برقرار نشد.\nلطفاً چند لحظه بعد دوباره تلاش کنید.",
        Language.en: "⚠️ Couldn't reach the server.\nPlease try again in a moment.",
        Language.ru: "⚠️ Не удалось связаться с сервером.\nПожалуйста, повторите попытку чуть позже.",
    },
    "status": {
        Language.fa: "📊 وضعیت شما:\n• شناسه: {tg_id}\n• دعوت‌ها: {referrals}\n• حجم روزانه: {daily_limit}\n• کانفیگ‌های دریافتی: {configs}\n• مصرف: {usage}\n• زمان باقی‌مانده: {remaining}",
        Language.en: "📊 Your status:\n• ID: {tg_id}\n• Referrals: {referrals}\n• Daily limit: {daily_limit}\n• Configs received: {configs}\n• Usage: {usage}\n• Time left: {remaining}",
        Language.ru: "📊 Ваш статус:\n• ID: {tg_id}\n• Приглашения: {referrals}\n• Дневной лимит: {daily_limit}\n• Конфигов получено: {configs}\n• Расход: {usage}\n• Осталось: {remaining}",
    },
    "invite": {
        Language.fa: "👥 دوستان خود را دعوت کنید!\nلینک دعوت شما:\n{link}\n\nتعداد دعوت‌ها: {count}\nحجم روزانهٔ فعلی: {daily_size}",
        Language.en: "👥 Invite your friends!\nYour invite link:\n{link}\n\nInvites: {count}\nCurrent daily size: {daily_size}",
        Language.ru: "👥 Приглашайте друзей!\nВаша ссылка:\n{link}\n\nПриглашений: {count}\nТекущий объём: {daily_size}",
    },
    "reminder_expired": {
        Language.fa: "⏳ کانفیگ آزمایشی شما منقضی شد.\nمی‌توانید همین حالا یک کانفیگ تازه بگیرید.",
        Language.en: "⏳ Your trial config has expired.\nYou can grab a fresh one now.",
        Language.ru: "⏳ Ваш пробный конфиг истёк.\nМожете получить новый прямо сейчас.",
    },
    "reminder_limited": {
        Language.fa: "📉 حجم کانفیگ آزمایشی شما تمام شد.\nفردا یکی تازه بگیرید یا دوستان خود را دعوت کنید.",
        Language.en: "📉 Your trial config ran out of data.\nGet a fresh one tomorrow, or invite friends.",
        Language.ru: "📉 Трафик пробного конфига закончился.\nПолучите новый завтра или пригласите друзей.",
    },
    "settings_menu": {
        Language.fa: "⚙️ تنظیمات:\nزبان و یادآوری‌ها را اینجا تغییر دهید.",
        Language.en: "⚙️ Settings:\nChange your language and reminders here.",
        Language.ru: "⚙️ Настройки:\nИзмените язык и напоминания здесь.",
    },
    "referral_joined": {
        Language.fa: "🎉 یکی از دوستانی که دعوت کردید اولین کانفیگش را گرفت!\nتعداد دعوت‌های شما: {count}\nحجم روزانهٔ فعلی شما: {size}",
        Language.en: "🎉 A friend you invited just claimed their first config!\nYour invites: {count}\nYour daily allowance is now: {size}",
        Language.ru: "🎉 Приглашённый вами друг получил свой первый конфиг!\nВаши приглашения: {count}\nВаш дневной лимит теперь: {size}",
    },
    "required_apps": {
        Language.fa: "🔗 برای استفاده از کانفیگ، یکی از این برنامه‌ها را نصب کنید:\n\n• اندروید: v2rayNG یا Hiddify\n• آیفون: Streisand یا Hiddify\n• ویندوز: Hiddify یا v2rayN\n• مک: Streisand یا Hiddify\n\nسپس کانفیگ را کپی کرده و در برنامه وارد (Import) کنید.",
        Language.en: "🔗 To use your config, install one of these apps:\n\n• Android: v2rayNG or Hiddify\n• iOS: Streisand or Hiddify\n• Windows: Hiddify or v2rayN\n• macOS: Streisand or Hiddify\n\nThen copy your config and import it into the app.",
        Language.ru: "🔗 Чтобы использовать конфиг, установите одно из приложений:\n\n• Android: v2rayNG или Hiddify\n• iOS: Streisand или Hiddify\n• Windows: Hiddify или v2rayN\n• macOS: Streisand или Hiddify\n\nЗатем скопируйте конфиг и импортируйте его в приложение.",
    },
    "banned": {
        Language.fa: "⛔️ دسترسی شما به ربات مسدود شده است.",
        Language.en: "⛔️ Your access to the bot has been blocked.",
        Language.ru: "⛔️ Ваш доступ к боту заблокирован.",
    },
}


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    engine = create_engine(settings.database_url)
    sessionmaker = create_sessionmaker(engine)
    try:
        async with sessionmaker() as session:
            settings_repo = SettingsRepository(session)
            content_repo = ContentRepository(session)
            for key, value in DEFAULT_SETTINGS.items():
                await settings_repo.add_default(key, value)
            for key, bodies in DEFAULT_CONTENT.items():
                for lang, body in bodies.items():
                    await content_repo.add_default(key, lang, body)
            await session.commit()
        logger.info(
            "seed: ensured %d settings + %d content keys (defaults only, existing rows untouched)",
            len(DEFAULT_SETTINGS),
            len(DEFAULT_CONTENT),
        )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
