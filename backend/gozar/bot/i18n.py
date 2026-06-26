"""In-code i18n for fixed UI chrome (button labels).

Message *bodies* come from the ``content`` table via ContentService; only the small set of fixed
button labels lives here. ``t(key, lang)`` falls back to Farsi, then to the key itself.
"""

from __future__ import annotations

from gozar.db.models.enums import Language

_LABELS: dict[str, dict[Language, str]] = {
    "menu_config": {
        Language.fa: "🎁 کانفیگ امروز",
        Language.en: "🎁 Today's config",
        Language.ru: "🎁 Конфиг на сегодня",
    },
    "menu_invite": {
        Language.fa: "👥 دعوت دوستان",
        Language.en: "👥 Invite friends",
        Language.ru: "👥 Пригласить друзей",
    },
    "menu_status": {
        Language.fa: "📊 وضعیت من",
        Language.en: "📊 My status",
        Language.ru: "📊 Мой статус",
    },
    "menu_help": {
        Language.fa: "❓ راهنما",
        Language.en: "❓ Help",
        Language.ru: "❓ Помощь",
    },
    "menu_settings": {
        Language.fa: "⚙️ تنظیمات",
        Language.en: "⚙️ Settings",
        Language.ru: "⚙️ Настройки",
    },
    "back": {
        Language.fa: "⬅️ بازگشت",
        Language.en: "⬅️ Back",
        Language.ru: "⬅️ Назад",
    },
    "change_location": {
        Language.fa: "🌍 تغییر لوکیشن",
        Language.en: "🌍 Change location",
        Language.ru: "🌍 Сменить локацию",
    },
    "coming_soon": {
        Language.fa: "به‌زودی…",
        Language.en: "Coming soon…",
        Language.ru: "Скоро…",
    },
}

# Language-picker captions: each language's own name (identical regardless of the current language).
LANGUAGE_NAMES: dict[Language, str] = {
    Language.fa: "فارسی 🇮🇷",
    Language.en: "English 🇬🇧",
    Language.ru: "Русский 🇷🇺",
}


def t(key: str, lang: Language) -> str:
    labels = _LABELS.get(key, {})
    return labels.get(lang) or labels.get(Language.fa) or key
