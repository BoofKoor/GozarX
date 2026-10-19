"""In-code copy of the Telegram console (``/admin``): titles, table labels, short notes, the
buttons that are not in the operator-editable catalogue.

The console's PROSE that the operator may want to word themselves — prompts, confirmations, results
— stays in the ``content`` table (``admin_*`` keys). What lives here is chrome: the words of a table
header or a one-line state, which change with the code that fills them. The screens the console has
had since Phase 6 carry all three languages, like the rest of the bot's chrome; the operations
screens added from Phase 30 on are written in Persian only (their operators are), so ``tr`` falls
back to Persian like ``ui.labels.t``.

Placeholders are ``{name}`` fields filled by ``tr(key, lang, **values)`` — always from code, never
from a user's text — and every value handed in is HTML already (escape it first).
"""

from __future__ import annotations

from gozar.db.models.enums import Language

fa, en, ru = Language.fa, Language.en, Language.ru

TEXT: dict[str, dict[Language, str]] = {
    # ---- home ----------------------------------------------------------------------------------
    "home_title": {fa: "🛠 پنل مدیریت گذر", en: "🛠 Gozar console", ru: "🛠 Панель Gozar"},
    "home_users": {fa: "👥 کاربران", en: "👥 Users", ru: "👥 Пользователи"},
    "home_users_val": {fa: "{total} • امروز +{new}", en: "{total} • today +{new}", ru: "{total} • сегодня +{new}"},
    "home_claims": {fa: "📥 کانفیگ امروز", en: "📥 Configs today", ru: "📥 Конфигов сегодня"},
    "home_active": {fa: "🟢 کانفیگ فعال", en: "🟢 Active configs", ru: "🟢 Активных конфигов"},
    "home_online": {fa: "📶 آنلاین اسکواد", en: "📶 Squad online", ru: "📶 Онлайн в скваде"},
    "home_online_val": {fa: "{now} از {week} در این هفته", en: "{now} of {week} this week", ru: "{now} из {week} за неделю"},
    "home_footer": {fa: "⏱ {time}", en: "⏱ {time}", ru: "⏱ {time}"},
    "notice_blocked": {
        fa: "⚠️ تلگرام ایموجی‌های پرمیوم را نپذیرفت (اشتراک پرمیوم اکانتی که ربات را ساخته فعال است؟). تا فردا ایموجی معمولی نشان داده می‌شود؛ از «🎨 ظاهر» همین حالا دوباره امتحان کن.",
        en: "⚠️ Telegram didn't accept the premium emoji (is Premium active on the account that created the bot?). Plain emoji until tomorrow; retry now from «🎨 Appearance».",
        ru: "⚠️ Telegram не принял премиум-эмодзи (активен ли Premium у аккаунта-владельца бота?). До завтра — обычные эмодзи; повторить можно в «🎨 Внешний вид».",
    },
    # ---- stats ---------------------------------------------------------------------------------
    "stats_title": {fa: "📊 آمار ربات", en: "📊 Bot stats", ru: "📊 Статистика бота"},
    "stats_users": {fa: "کاربران", en: "Users", ru: "Пользователи"},
    "stats_total": {fa: "کل", en: "Total", ru: "Всего"},
    "stats_available": {fa: "آزاد", en: "Available", ru: "Свободны"},
    "stats_active": {fa: "کانفیگ فعال", en: "Active config", ru: "С конфигом"},
    "stats_banned": {fa: "مسدود", en: "Banned", ru: "Заблокированы"},
    "stats_referrals": {fa: "مجموع دعوت‌ها", en: "Total referrals", ru: "Всего приглашений"},
    "stats_today": {fa: "امروز", en: "Today", ru: "Сегодня"},
    "stats_claims": {fa: "کانفیگ‌ها", en: "Configs", ru: "Конфиги"},
    "stats_new": {fa: "کاربر جدید", en: "New users", ru: "Новые"},
    "stats_active_users": {fa: "کاربر فعال", en: "Active users", ru: "Активные"},
    "stats_week": {fa: "۷ روز اخیر", en: "Last 7 days", ru: "Последние 7 дней"},
    "stats_day": {fa: "روز", en: "Day", ru: "День"},
    "stats_signups": {fa: "عضو جدید", en: "Signups", ru: "Регистрации"},
    "stats_locations": {fa: "لوکیشن‌های امروز", en: "Today's locations", ru: "Локации сегодня"},
    "stats_location": {fa: "لوکیشن", en: "Location", ru: "Локация"},
    "stats_more": {fa: "و {n} لوکیشن دیگر", en: "and {n} more", ru: "и ещё {n}"},
    "stats_top": {fa: "بیشترین دعوت", en: "Top inviters", ru: "Больше всех пригласили"},
    "stats_user": {fa: "کاربر", en: "User", ru: "Пользователь"},
    "stats_invites": {fa: "دعوت", en: "Invites", ru: "Приглашения"},
    # ---- user card -----------------------------------------------------------------------------
    "user_title": {fa: "👤 کاربر {id}", en: "👤 User {id}", ru: "👤 Пользователь {id}"},
    "user_status": {fa: "وضعیت", en: "Status", ru: "Статус"},
    "user_language": {fa: "زبان", en: "Language", ru: "Язык"},
    "user_referrals": {fa: "دعوت‌ها", en: "Referrals", ru: "Приглашения"},
    "user_configs": {fa: "کانفیگ‌های دریافتی", en: "Configs received", ru: "Получено конфигов"},
    "user_last": {fa: "آخرین کانفیگ", en: "Last config", ru: "Последний конфиг"},
    "user_panel": {fa: "نام پنل", en: "Panel name", ru: "Имя в панели"},
    "user_joined": {fa: "عضویت", en: "Joined", ru: "Регистрация"},
    "user_reach": {fa: "دسترسی", en: "Reachable", ru: "Доступен"},
    "user_unreachable": {fa: "⚠️ از {time} پیام نمی‌رسد", en: "⚠️ not since {time}", ru: "⚠️ нет с {time}"},
    "user_recent": {fa: "آخرین کانفیگ‌ها", en: "Recent configs", ru: "Последние конфиги"},
    "user_when": {fa: "زمان", en: "When", ru: "Когда"},
    "status_available": {fa: "⚪️ آزاد", en: "⚪️ Available", ru: "⚪️ Свободен"},
    "status_active_config": {fa: "🟢 کانفیگ فعال", en: "🟢 Active config", ru: "🟢 С конфигом"},
    "status_banned": {fa: "⛔️ مسدود", en: "⛔️ Banned", ru: "⛔️ Заблокирован"},
    "copy": {fa: "📑 کپی", en: "📑 Copy", ru: "📑 Копировать"},
    # ---- locations -----------------------------------------------------------------------------
    "loc_title": {fa: "📍 لوکیشن‌ها", en: "📍 Locations", ru: "📍 Локации"},
    "loc_squad": {fa: "اسکواد آزمایشی", en: "Trial squad", ru: "Пробный сквад"},
    "loc_count": {fa: "{n} لوکیشن در منوی کاربرها", en: "{n} locations in the users' picker", ru: "{n} локаций в меню"},
    "loc_name": {fa: "لوکیشن", en: "Location", ru: "Локация"},
    "loc_today": {fa: "کانفیگ امروز", en: "Configs today", ru: "Сегодня"},
    "loc_no_squad": {
        fa: "اسکواد آزمایشی هنوز انتخاب نشده (پنل وب ← تنظیمات).",
        en: "No trial squad yet (web panel → Settings).",
        ru: "Пробный сквад ещё не выбран (веб-панель → Настройки).",
    },
    "loc_panel_error": {fa: "⚠️ پنل جواب نداد؛ کمی بعد دوباره امتحان کن.", en: "⚠️ The panel didn't answer; try again shortly.", ru: "⚠️ Панель не ответила; попробуйте позже."},
    "loc_none": {fa: "این اسکواد هیچ لوکیشن فعالی ندارد.", en: "This squad serves no live location.", ru: "Сквад не обслуживает ни одной локации."},
    "loc_all_note": {
        fa: "کاربرها همهٔ لوکیشن‌های این اسکواد را می‌بینند؛ هاستی که بعداً اضافه شود خودش می‌آید.",
        en: "Users see every location of this squad; a host added later appears by itself.",
        ru: "Пользователи видят все локации сквада; новый хост появится сам.",
    },
    "loc_subset_note": {
        fa: "فقط لوکیشن‌های انتخاب‌شده در پنل وب نشان داده می‌شوند ({n} از {total}).",
        en: "Only the locations picked in the web panel are offered ({n} of {total}).",
        ru: "Показаны только выбранные в веб-панели локации ({n} из {total}).",
    },
    "btn_refresh": {fa: "🔄 همهٔ لوکیشن‌ها", en: "🔄 Offer all", ru: "🔄 Показать все"},
    # ---- look ----------------------------------------------------------------------------------
    "look_title": {fa: "🎨 ظاهر", en: "🎨 Appearance", ru: "🎨 Внешний вид"},
    "look_premium": {fa: "ایموجی پرمیوم", en: "Premium emoji", ru: "Премиум-эмодзи"},
    "look_rich": {fa: "پیام ریچ (جدول‌دار)", en: "Rich messages", ru: "Rich-сообщения"},
    "look_telegram": {fa: "تلگرام", en: "Telegram", ru: "Telegram"},
    "look_check": {fa: "بررسی شناسه‌ها", en: "Emoji ids check", ru: "Проверка id"},
    "look_on": {fa: "✅ روشن", en: "✅ On", ru: "✅ Вкл"},
    "look_off": {fa: "⚪️ خاموش", en: "⚪️ Off", ru: "⚪️ Выкл"},
    "look_ok": {fa: "✅ قبول می‌کند", en: "✅ accepts them", ru: "✅ принимает"},
    "look_blocked": {fa: "⛔️ نپذیرفت: {reason}", en: "⛔️ refused: {reason}", ru: "⛔️ отклонил: {reason}"},
    "look_checked": {fa: "{time} • {missing} ناشناخته", en: "{time} • {missing} unknown", ru: "{time} • {missing} неизвестных"},
    "look_never": {fa: "هنوز انجام نشده", en: "not run yet", ru: "ещё не было"},
    "look_help": {
        fa: "ایموجی پرمیوم فقط وقتی دیده می‌شود که اکانتی که ربات را در BotFather ساخته Telegram Premium داشته باشد؛ پرچم لوکیشن‌ها در منوی کاربرها هم از همین پیروی می‌کند. پیام ریچ فقط برای همین پنل است و اپ تلگرام به‌روز می‌خواهد. اگر صفحه‌ای درست دیده نشد، /simple را بزن.",
        en: "Premium emoji show only while the account that created the bot in BotFather has Telegram Premium; the users' location flags follow the same switch. Rich messages are for this console only and need an up-to-date Telegram app. If a screen looks wrong, send /simple.",
        ru: "Премиум-эмодзи видны, только пока у аккаунта, создавшего бота в BotFather, есть Telegram Premium; флаги локаций у пользователей следуют этому же переключателю. Rich-сообщения — только для этой панели и требуют свежей версии Telegram. Если экран выглядит неверно, отправьте /simple.",
    },
    "btn_premium_on": {fa: "💎 پرمیوم: روشن", en: "💎 Premium: on", ru: "💎 Премиум: вкл"},
    "btn_premium_off": {fa: "💎 پرمیوم: خاموش", en: "💎 Premium: off", ru: "💎 Премиум: выкл"},
    "btn_rich_on": {fa: "📰 ریچ: روشن", en: "📰 Rich: on", ru: "📰 Rich: вкл"},
    "btn_rich_off": {fa: "📰 ریچ: خاموش", en: "📰 Rich: off", ru: "📰 Rich: выкл"},
    "btn_test": {fa: "🧪 تست ظاهر", en: "🧪 Test the look", ru: "🧪 Проверить вид"},
    "btn_retry": {fa: "🔁 دوباره امتحان کن", en: "🔁 Try premium again", ru: "🔁 Повторить премиум"},
    "test_sample": {
        fa: "🧪 <b>نمونهٔ متن</b>\n🏠 منو • 🔑 کلید • 🗑 حذف • 🔄 بروزرسانی • ⏳ در حال اجرا\nپرچم‌ها: 🇩🇪 🇳🇱 🇫🇮 🇺🇸 🇬🇧 🇹🇷",
        en: "🧪 <b>Sample text</b>\n🏠 menu • 🔑 key • 🗑 delete • 🔄 refresh • ⏳ running\nFlags: 🇩🇪 🇳🇱 🇫🇮 🇺🇸 🇬🇧 🇹🇷",
        ru: "🧪 <b>Пример текста</b>\n🏠 меню • 🔑 ключ • 🗑 удалить • 🔄 обновить • ⏳ выполняется\nФлаги: 🇩🇪 🇳🇱 🇫🇮 🇺🇸 🇬🇧 🇹🇷",
    },
    "test_table": {fa: "🧪 نمونهٔ پیام ریچ", en: "🧪 Rich message sample", ru: "🧪 Пример rich-сообщения"},
    "test_details": {fa: "یک بخش جمع‌شونده", en: "A folding section", ru: "Сворачиваемый блок"},
    "test_question": {
        fa: "بالا یک متن با آیکون‌های پرمیوم، یک پیام ریچ با جدول و دکمه‌های رنگی هست. درست دیده می‌شوند؟",
        en: "Above: a text with premium icons, a rich message with a table, and coloured buttons. Do they look right?",
        ru: "Выше: текст с премиум-иконками, rich-сообщение с таблицей и цветные кнопки. Всё выглядит верно?",
    },
    "btn_test_yes": {fa: "✅ آره، درسته", en: "✅ Yes, all good", ru: "✅ Да, всё верно"},
    "btn_test_no": {fa: "❌ نه، ساده‌اش کن", en: "❌ No, go simple", ru: "❌ Нет, упростить"},
    "simple_done": {
        fa: "حالت ساده روشن شد: ایموجی معمولی و پیام معمولی. برگرداندن: /admin ← 🎨 ظاهر.",
        en: "Simple mode is on: plain emoji, regular messages. To undo: /admin → 🎨 Appearance.",
        ru: "Простой режим включён: обычные эмодзи и сообщения. Вернуть: /admin → 🎨 Внешний вид.",
    },
    "saved": {fa: "ذخیره شد", en: "Saved", ru: "Сохранено"},
    "sample_tap": {fa: "این فقط یک دکمهٔ نمونه است", en: "Just a sample button", ru: "Это просто пример"},
    "sample_green": {fa: "سبز", en: "Green", ru: "Зелёная"},
    "sample_blue": {fa: "آبی", en: "Blue", ru: "Синяя"},
    "sample_red": {fa: "قرمز", en: "Red", ru: "Красная"},
}  # fmt: skip


def tr(key: str, lang: Language, **values: object) -> str:
    """The console text ``key`` in ``lang`` (Persian when that language has none), with its
    ``{name}`` fields filled from ``values``."""
    texts = TEXT.get(key, {})
    text = texts.get(lang) or texts.get(Language.fa) or key
    return text.format(**values) if values else text
