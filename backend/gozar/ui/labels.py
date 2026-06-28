"""In-code i18n for fixed UI chrome (button labels).

Message *bodies* come from the ``content`` table via ContentService; only the small set of fixed
button labels lives here. ``t(key, lang)`` falls back to Farsi, then to the key itself.

These are the **default** labels; the admin panel can override them per-language via the
``button_configs`` table (see ``services.button_service``). This map is always the fallback.
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
        Language.fa: "🔄 تغییر لوکیشن",
        Language.en: "🔄 Change location",
        Language.ru: "🔄 Изменить локацию",
    },
    "get_config": {
        Language.fa: "📥 دریافت کانفیگ",
        Language.en: "📥 Get config",
        Language.ru: "📥 Получить конфиг",
    },
    "show_menu": {
        Language.fa: "🏠 نمایش منوی اصلی",
        Language.en: "🏠 Main menu",
        Language.ru: "🏠 Главное меню",
    },
    "settings_language": {
        Language.fa: "🌐 تغییر زبان",
        Language.en: "🌐 Change language",
        Language.ru: "🌐 Сменить язык",
    },
    # Reminder toggle on the settings keyboard — label shows the CURRENT state; a tap flips it.
    "reminder_on": {
        Language.fa: "🔔 یادآور: روشن",
        Language.en: "🔔 Reminders: on",
        Language.ru: "🔔 Напоминания: вкл",
    },
    "reminder_off": {
        Language.fa: "🔕 یادآور: خاموش",
        Language.en: "🔕 Reminders: off",
        Language.ru: "🔕 Напоминания: выкл",
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
    # --- Admin panel (owner-only) chrome ---
    "admin_stats": {
        Language.fa: "📊 آمار",
        Language.en: "📊 Stats",
        Language.ru: "📊 Статистика",
    },
    "admin_users": {
        Language.fa: "👤 مدیریت کاربر",
        Language.en: "👤 User lookup",
        Language.ru: "👤 Пользователь",
    },
    "admin_broadcast": {
        Language.fa: "📣 پیام همگانی",
        Language.en: "📣 Broadcast",
        Language.ru: "📣 Рассылка",
    },
    "admin_forward": {
        Language.fa: "↪️ فوروارد همگانی",
        Language.en: "↪️ Forward",
        Language.ru: "↪️ Переслать всем",
    },
    "admin_refresh_locations": {
        Language.fa: "📍 بروزرسانی لوکیشن‌ها",
        Language.en: "📍 Refresh locations",
        Language.ru: "📍 Обновить локации",
    },
    "admin_reset_all": {
        Language.fa: "♻️ ریست حجم همه",
        Language.en: "♻️ Reset all traffic",
        Language.ru: "♻️ Сбросить трафик",
    },
    "admin_close": {
        Language.fa: "❌ بستن",
        Language.en: "❌ Close",
        Language.ru: "❌ Закрыть",
    },
    "admin_back": {
        Language.fa: "🔙 منوی ادمین",
        Language.en: "🔙 Admin menu",
        Language.ru: "🔙 Админ-меню",
    },
    "admin_send": {
        Language.fa: "✅ ارسال",
        Language.en: "✅ Send",
        Language.ru: "✅ Отправить",
    },
    "admin_confirm": {
        Language.fa: "✅ تأیید",
        Language.en: "✅ Confirm",
        Language.ru: "✅ Подтвердить",
    },
    "admin_cancel": {
        Language.fa: "❌ لغو",
        Language.en: "❌ Cancel",
        Language.ru: "❌ Отмена",
    },
    "admin_ban": {
        Language.fa: "⛔ مسدودسازی",
        Language.en: "⛔ Ban",
        Language.ru: "⛔ Бан",
    },
    "admin_unban": {
        Language.fa: "✅ رفع مسدودی",
        Language.en: "✅ Unban",
        Language.ru: "✅ Разбан",
    },
    "admin_reclaim": {
        Language.fa: "🔄 اجازه دریافت مجدد",
        Language.en: "🔄 Allow re-claim",
        Language.ru: "🔄 Разрешить заново",
    },
    "admin_zero_referrals": {
        Language.fa: "0️⃣ صفر کردن دعوت‌ها",
        Language.en: "0️⃣ Zero referrals",
        Language.ru: "0️⃣ Обнулить рефералов",
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
