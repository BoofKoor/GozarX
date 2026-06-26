"""In-code i18n for fixed UI chrome (button labels).

Message *bodies* come from the ``content`` table via ContentService; only the small set of fixed
button labels lives here. ``t(key, lang)`` falls back to Farsi, then to the key itself.
"""

from __future__ import annotations

from gozar.db.models.enums import Language

_LABELS: dict[str, dict[Language, str]] = {
    "menu_config": {
        Language.fa: "📥 دریافت کانفیگ امروز",
        Language.en: "📥 Get today's config",
        Language.ru: "📥 Получить конфиг на сегодня",
    },
    "menu_invite": {
        Language.fa: "🗳 دعوت دوستان",
        Language.en: "🗳 Invite friends",
        Language.ru: "🗳 Пригласить друзей",
    },
    "menu_status": {
        Language.fa: "📊 وضعیت من",
        Language.en: "📊 My status",
        Language.ru: "📊 Мой статус",
    },
    "menu_help": {
        Language.fa: "📝 راهنما",
        Language.en: "📝 Help",
        Language.ru: "📝 Помощь",
    },
    "menu_settings": {
        Language.fa: "⚙️ تنظیمات",
        Language.en: "⚙️ Settings",
        Language.ru: "⚙️ Настройки",
    },
    "back": {
        Language.fa: "🏠 بازگشت",
        Language.en: "🏠 Back",
        Language.ru: "🏠 Назад",
    },
    "change_location": {
        Language.fa: "🌍 تغییر لوکیشن",
        Language.en: "🌍 Change location",
        Language.ru: "🌍 Сменить локацию",
    },
    "settings_language": {
        Language.fa: "🌐 تغییر زبان",
        Language.en: "🌐 Change language",
        Language.ru: "🌐 Сменить язык",
    },
    "reminder_on": {
        Language.fa: "📮 یادآور ✅",
        Language.en: "📮 Reminders ✅",
        Language.ru: "📮 Напоминания ✅",
    },
    "reminder_off": {
        Language.fa: "📮 یادآور ❌",
        Language.en: "📮 Reminders ❌",
        Language.ru: "📮 Напоминания ❌",
    },
    "invite_share": {
        Language.fa: "📤 اشتراک‌گذاری لینک",
        Language.en: "📤 Share link",
        Language.ru: "📤 Поделиться ссылкой",
    },
    "increase_traffic": {
        Language.fa: "🔋 افزایش حجم روزانه (رایگان)",
        Language.en: "🔋 Increase daily traffic (free)",
        Language.ru: "🔋 Увеличить ежедневный трафик (бесплатно)",
    },
    "apps": {
        Language.fa: "🔗 برنامه مورد نیاز",
        Language.en: "🔗 Required apps",
        Language.ru: "🔗 Необходимые приложения",
    },
    "nav_prev": {
        Language.fa: "⬅️ قبلی",
        Language.en: "⬅️ Prev",
        Language.ru: "⬅️ Назад",
    },
    "nav_next": {
        Language.fa: "بعدی ➡️",
        Language.en: "Next ➡️",
        Language.ru: "Вперёд ➡️",
    },
    "coming_soon": {
        Language.fa: "به‌زودی…",
        Language.en: "Coming soon…",
        Language.ru: "Скоро…",
    },
}

# Language-picker captions: each language's own name (identical regardless of the current language).
LANGUAGE_NAMES: dict[Language, str] = {
    Language.fa: "🇮🇷 فارسی",
    Language.en: "🇬🇧 English",
    Language.ru: "🇷🇺 Русский",
}


def t(key: str, lang: Language) -> str:
    labels = _LABELS.get(key, {})
    return labels.get(lang) or labels.get(Language.fa) or key
