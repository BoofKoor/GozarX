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
from gozar.db.repositories.site_landing_page import SiteLandingPageRepository
from gozar.db.session import create_engine, create_sessionmaker
from gozar.seed_landings import DEFAULT_SITE_LANDINGS
from gozar.services.settings_service import SettingKey, SiteSettingKey

logger = logging.getLogger("gozar.seed")

# Trial economics — editable from the panel. (trial squad + locations are wizard-only.)
DEFAULT_SETTINGS: dict[str, str] = {
    SettingKey.DAILY_LIMIT_MB: "1024",
    SettingKey.REFERRAL_REWARD_MB: "500",
    SettingKey.REFERRAL_REWARD_LIMIT: "10",
    SettingKey.TRIAL_HOURS: "24",
    SettingKey.ADS_ENABLED: "false",
    SettingKey.CONFIGS_PER_PAGE: "8",
    SettingKey.AD_BUTTON_ENABLED: "false",
    SettingKey.AD_BUTTON_TEXT: "",
    SettingKey.AD_BUTTON_URL: "",
    SettingKey.AD_BUTTON_EMOJI_ID: "",
}

# Website economics — a SEPARATE economy, editable from the panel's 'website' section.
# site_trial_squad + site_locations are wizard-picked (not seeded), like their bot counterparts.
DEFAULT_SITE_SETTINGS: dict[str, str] = {
    SiteSettingKey.SITE_TRIAL_HOURS: "24",
    SiteSettingKey.SITE_DAILY_LIMIT_MB: "1024",
    SiteSettingKey.SITE_REFERRAL_REWARD_MB: "500",
    SiteSettingKey.SITE_REFERRAL_REWARD_LIMIT: "10",
    SiteSettingKey.SITE_REWARD_PWA_MB: "200",
    SiteSettingKey.SITE_REWARD_PUSH_MB: "150",
    SiteSettingKey.SITE_REWARD_STREAK_MB: "300",
    SiteSettingKey.SITE_STREAK_DAYS: "7",
}

# Core user-facing copy per language; placeholders are {token}. Button labels live in the in-code
# i18n map (Phase 3), NOT here.
DEFAULT_CONTENT: dict[str, dict[Language, str]] = {
    "welcome": {
        Language.fa: "سلام! 👋\nهر روز یک کانفیگ آزمایشی رایگان از منوی زیر بگیر، و با دعوت دوستانت حجم روزانه‌ات را بیشتر کن. 🚀",
        Language.en: "Hey there! 👋\nGrab a free trial config every day from the menu below, and invite friends to grow your daily traffic. 🚀",
        Language.ru: "Привет! 👋\nКаждый день получай бесплатный пробный конфиг из меню ниже и приглашай друзей, чтобы увеличить дневной трафик. 🚀",
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
    # Shown on the get-config landing when the trial's DATA is spent but its time is still valid: the
    # SAME config revives the moment a friend is invited (referral traffic bump), so we nudge to invite
    # rather than imply the config is gone. The landing already carries the 🔋 invite button.
    "config_limited": {
        Language.fa: "🪫 حجم کانفیگ شما تمام شده، اما هنوز معتبر است.\n⏳ زمان باقی‌مانده: {remaining}\n📊 مصرف: {usage} از {total}\n👥 با دعوت دوستان حجم بگیرید تا همین کانفیگ دوباره وصل شود.",
        Language.en: "🪫 Your config is out of data but still valid.\n⏳ Time left: {remaining}\n📊 Used: {usage} of {total}\n👥 Invite friends to top up and revive this same config.",
        Language.ru: "🪫 Трафик конфига закончился, но он ещё действует.\n⏳ Осталось: {remaining}\n📊 Израсходовано: {usage} из {total}\n👥 Пригласите друзей, чтобы пополнить трафик и снова активировать этот конфиг.",
    },
    "config_delivered": {
        Language.fa: "کانفیگ شما برای «{location}» آماده است:\n\n<code>{link}</code>\n\n⏳ اعتبار تا: {expires}",
        Language.en: 'Your config for "{location}" is ready:\n\n<code>{link}</code>\n\n⏳ Valid until: {expires}',
        Language.ru: "Ваш конфиг для «{location}» готов:\n\n<code>{link}</code>\n\n⏳ Действует до: {expires}",
    },
    # Toast shown at the top of the chat the moment a fresh config is created (claim path only).
    "config_created_toast": {
        Language.fa: "✅ کانفیگ با موفقیت ساخته شد",
        Language.en: "✅ Config created successfully",
        Language.ru: "✅ Конфиг успешно создан",
    },
    "already_claimed": {
        Language.fa: "شما به‌تازگی کانفیگ گرفته‌اید. ✅\nتا {retry_after} دیگر می‌توانید کانفیگ بعدی را بگیرید، یا با دعوت دوستان حجم خود را زیاد کنید.",
        Language.en: "You've recently claimed a config. ✅\nYou can get the next one in {retry_after}, or invite friends for more.",
        Language.ru: "Вы недавно получили конфиг. ✅\nСледующий можно получить через {retry_after} или пригласите друзей.",
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
        Language.fa: "📊 وضعیت شما:\n{status_line}\n• شناسه: {tg_id}\n• دعوت‌ها: {referrals}\n• حجم روزانه: {daily_limit}\n• کانفیگ‌های دریافتی: {configs}{status_usage}",
        Language.en: "📊 Your status:\n{status_line}\n• ID: {tg_id}\n• Referrals: {referrals}\n• Daily limit: {daily_limit}\n• Configs received: {configs}{status_usage}",
        Language.ru: "📊 Ваш статус:\n{status_line}\n• ID: {tg_id}\n• Приглашения: {referrals}\n• Дневной лимит: {daily_limit}\n• Конфигов получено: {configs}{status_usage}",
    },
    "status_received": {
        Language.fa: "کانفیگ دریافت شده ✅",
        Language.en: "Config received ✅",
        Language.ru: "Конфиг получен ✅",
    },
    "status_not_received": {
        Language.fa: "کانفیگ دریافت نشده❕",
        Language.en: "Config not received❕",
        Language.ru: "Конфиг не получен❕",
    },
    "status_usage": {
        Language.fa: "\n• مصرف: {usage}\n• زمان باقی‌مانده: {remaining}",
        Language.en: "\n• Usage: {usage}\n• Time left: {remaining}",
        Language.ru: "\n• Расход: {usage}\n• Осталось: {remaining}",
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
    # The reminder messages can use the global variables {total_traffic} / {used_traffic} / {expire}
    # / {cooldown_remaining} (filled from the panel webhook / reconcile job). They render to "—" for
    # any value the event doesn't carry.
    "reminder_limited": {
        Language.fa: "🪫 حجم کانفیگ شما تمام شد، اما کانفیگ‌تان هنوز معتبر است.\n🔋 حجم کل: {total_traffic} · مصرف‌شده: {used_traffic}\n👥 همین حالا دوستی را دعوت کنید تا حجم بیشتری بگیرید و همین کانفیگ دوباره وصل شود.",
        Language.en: "🪫 Your config ran out of data, but it's still valid.\n🔋 Total: {total_traffic} · Used: {used_traffic}\n👥 Invite a friend now to get more data and revive this same config.",
        Language.ru: "🪫 Трафик конфига закончился, но сам конфиг ещё действует.\n🔋 Всего: {total_traffic} · Использовано: {used_traffic}\n👥 Пригласите друга, чтобы получить больше трафика и снова активировать этот конфиг.",
    },
    "settings_menu": {
        Language.fa: "⚙️ تنظیمات:\nزبان و یادآوری‌ها را اینجا تغییر دهید.",
        Language.en: "⚙️ Settings:\nChange your language and reminders here.",
        Language.ru: "⚙️ Настройки:\nИзмените язык и напоминания здесь.",
    },
    # Toasts shown when the settings reminder toggle flips (callback.answer), not full screens.
    "reminder_enabled": {
        Language.fa: "🔔 یادآوری روشن شد. پیش از پایان اعتبار کانفیگ به شما یادآوری می‌کنیم.",
        Language.en: "🔔 Reminders on. We'll remind you before your config expires.",
        Language.ru: "🔔 Напоминания включены. Мы напомним до истечения конфига.",
    },
    "reminder_disabled": {
        Language.fa: "🔕 یادآوری خاموش شد.",
        Language.en: "🔕 Reminders off.",
        Language.ru: "🔕 Напоминания отключены.",
    },
    "ads": {
        Language.fa: "📣 از سرویس ما لذت می‌بری؟ آن را با دوستانت به اشتراک بگذار!",
        Language.en: "📣 Enjoying the service? Share it with your friends!",
        Language.ru: "📣 Нравится сервис? Поделитесь им с друзьями!",
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
    # --- Admin panel (owner-only) body copy. Operators read these in their own language. ---
    "admin_menu": {
        Language.fa: "🛠 پنل مدیریت\nیک گزینه را انتخاب کنید:",
        Language.en: "🛠 Admin panel\nChoose an option:",
        Language.ru: "🛠 Панель администратора\nВыберите действие:",
    },
    "admin_stats": {
        Language.fa: "📊 آمار ربات:\n• کل کاربران: {total}\n• آزاد: {available}\n• دارای کانفیگ فعال: {active}\n• مسدود: {banned}\n• کانفیگ‌های امروز: {configs_today}\n• مجموع دعوت‌ها: {referrals}",
        Language.en: "📊 Bot stats:\n• Total users: {total}\n• Available: {available}\n• Active config: {active}\n• Banned: {banned}\n• Configs today: {configs_today}\n• Total referrals: {referrals}",
        Language.ru: "📊 Статистика:\n• Всего пользователей: {total}\n• Свободны: {available}\n• С активным конфигом: {active}\n• Заблокированы: {banned}\n• Конфигов сегодня: {configs_today}\n• Всего приглашений: {referrals}",
    },
    "admin_broadcast_prompt": {
        Language.fa: "📣 پیامی که می‌خواهید برای همهٔ کاربران ارسال شود را بفرستید (متن یا رسانه).\nبدون سربرگ «فورواردشده» ارسال می‌شود.",
        Language.en: "📣 Send the message to broadcast to all users (text or media).\nIt is sent cleanly, without a 'Forwarded from' header.",
        Language.ru: "📣 Отправьте сообщение для рассылки всем (текст или медиа).\nОно уйдёт без пометки «Переслано».",
    },
    "admin_forward_prompt": {
        Language.fa: "↪️ پیامی را که می‌خواهید برای همهٔ کاربران فوروارد شود، فوروارد کنید.\nسربرگ «فورواردشده» حفظ می‌شود.",
        Language.en: "↪️ Forward the message you want forwarded to all users.\nThe 'Forwarded from' header is preserved.",
        Language.ru: "↪️ Перешлите сообщение, которое нужно переслать всем.\nПометка «Переслано» сохранится.",
    },
    "admin_send_preview": {
        Language.fa: "⬆️ پیش‌نمایش بالا دقیقاً همان چیزی است که کاربران می‌بینند.\nبه {count} کاربر ارسال شود؟",
        Language.en: "⬆️ The preview above is exactly what users will see.\nSend to {count} users?",
        Language.ru: "⬆️ Предпросмотр выше — это ровно то, что увидят пользователи.\nОтправить {count} пользователям?",
    },
    "admin_send_queued": {
        Language.fa: "✅ ارسال در صف قرار گرفت. پیشرفت در همین‌جا گزارش می‌شود.",
        Language.en: "✅ Queued. Progress will be reported here.",
        Language.ru: "✅ В очереди. Прогресс будет показан здесь.",
    },
    "admin_send_cancelled": {
        Language.fa: "❌ ارسال لغو شد.",
        Language.en: "❌ Send cancelled.",
        Language.ru: "❌ Отправка отменена.",
    },
    "admin_send_failed": {
        Language.fa: "⚠️ ارسال ممکن نشد (صف در دسترس نیست). بعداً تلاش کنید.",
        Language.en: "⚠️ Couldn't queue (queue unavailable). Try again later.",
        Language.ru: "⚠️ Не удалось поставить в очередь. Попробуйте позже.",
    },
    "admin_user_prompt": {
        Language.fa: "👤 شناسهٔ عددی تلگرام کاربر را بفرستید:",
        Language.en: "👤 Send the user's numeric Telegram ID:",
        Language.ru: "👤 Отправьте числовой Telegram ID пользователя:",
    },
    "admin_user_not_found": {
        Language.fa: "❓ کاربری با این شناسه پیدا نشد. دوباره تلاش کنید.",
        Language.en: "❓ No user with that ID. Try again.",
        Language.ru: "❓ Пользователь с таким ID не найден. Попробуйте снова.",
    },
    "admin_user_card": {
        Language.fa: "👤 کاربر {id}\n• وضعیت: {status}\n• زبان: {language}\n• دعوت‌ها: {referrals}\n• کانفیگ‌های دریافتی: {configs}\n• نام پنل: {panel}\n• تاریخ عضویت: {joined}",
        Language.en: "👤 User {id}\n• Status: {status}\n• Language: {language}\n• Referrals: {referrals}\n• Configs received: {configs}\n• Panel name: {panel}\n• Joined: {joined}",
        Language.ru: "👤 Пользователь {id}\n• Статус: {status}\n• Язык: {language}\n• Приглашения: {referrals}\n• Конфигов получено: {configs}\n• Имя в панели: {panel}\n• Регистрация: {joined}",
    },
    "admin_ban_confirm": {
        Language.fa: "⛔ این کاربر مسدود می‌شود و کانفیگ فعالش روی پنل حذف می‌شود. ادامه می‌دهید؟",
        Language.en: "⛔ This bans the user and deletes their live panel config. Continue?",
        Language.ru: "⛔ Пользователь будет заблокирован, а его активный конфиг на панели удалён. Продолжить?",
    },
    "admin_ban_done": {
        Language.fa: "⛔ کاربر مسدود شد و دسترسی پنل لغو شد.",
        Language.en: "⛔ User banned and panel access revoked.",
        Language.ru: "⛔ Пользователь заблокирован, доступ к панели отозван.",
    },
    "admin_unban_done": {
        Language.fa: "✅ مسدودی کاربر برداشته شد.",
        Language.en: "✅ User unbanned.",
        Language.ru: "✅ Пользователь разблокирован.",
    },
    "admin_reclaim_done": {
        Language.fa: "🔄 محدودیت دریافت امروز برداشته شد؛ کاربر می‌تواند دوباره کانفیگ بگیرد.",
        Language.en: "🔄 Today's claim was cleared; the user can claim a config again.",
        Language.ru: "🔄 Дневной лимит сброшен; пользователь может снова получить конфиг.",
    },
    "admin_zero_confirm": {
        Language.fa: "0️⃣ شمار دعوت‌های این کاربر صفر می‌شود و حجم روزانه‌اش به مقدار پایه برمی‌گردد. این عمل بازگشت‌پذیر نیست. ادامه می‌دهید؟",
        Language.en: "0️⃣ This zeroes the user's referrals and drops their daily allowance to base. This is not reversible. Continue?",
        Language.ru: "0️⃣ Приглашения пользователя обнулятся, а дневной объём вернётся к базовому. Это необратимо. Продолжить?",
    },
    "admin_zero_done": {
        Language.fa: "0️⃣ دعوت‌های کاربر صفر شد.",
        Language.en: "0️⃣ User's referrals reset to zero.",
        Language.ru: "0️⃣ Приглашения пользователя обнулены.",
    },
    "admin_reset_all_confirm": {
        Language.fa: "♻️ مصرف حجم {count} کاربر دارای کانفیگ فعال روی پنل صفر می‌شود. ادامه می‌دهید؟",
        Language.en: "♻️ This resets panel traffic consumption for {count} active users. Continue?",
        Language.ru: "♻️ Это сбросит расход трафика на панели для {count} активных пользователей. Продолжить?",
    },
    "admin_reset_all_queued": {
        Language.fa: "✅ ریست حجم در صف قرار گرفت. پیشرفت در همین‌جا گزارش می‌شود.",
        Language.en: "✅ Traffic reset queued. Progress will be reported here.",
        Language.ru: "✅ Сброс трафика в очереди. Прогресс будет показан здесь.",
    },
    "admin_refresh_done": {
        Language.fa: "📍 لوکیشن‌ها بروزرسانی شد ({count}): {locations}",
        Language.en: "📍 Locations refreshed ({count}): {locations}",
        Language.ru: "📍 Локации обновлены ({count}): {locations}",
    },
    "admin_refresh_failed": {
        Language.fa: "⚠️ بروزرسانی لوکیشن‌ها ممکن نشد (اسکواد آزمایشی تنظیم نشده یا خطای پنل).",
        Language.en: "⚠️ Couldn't refresh locations (trial squad not set, or a panel error).",
        Language.ru: "⚠️ Не удалось обновить локации (сквад не задан или ошибка панели).",
    },
}


# Website copy — a SEPARATE content namespace (``site_*`` keys) so it never appears in the bot's
# Texts editor, and vice-versa. Bilingual only (fa/en); the site has no Russian. Full microcopy lands
# with the site app (P8) — this is the SEO/hero starter set that establishes the pattern.
DEFAULT_SITE_CONTENT: dict[str, dict[Language, str]] = {
    "site_meta_title": {
        Language.fa: "گذرایکس — کانفیگ آزمایشی رایگان روزانه",
        Language.en: "GozarX — Free daily trial config",
    },
    "site_meta_description": {
        Language.fa: "هر روز یک کانفیگ آزمایشی رایگان بگیر — بدون ثبت‌نام، سریع و ساده. حجم روزانه‌ات را با دعوت دوستان بیشتر کن.",
        Language.en: "Get a free daily trial config — no signup, fast and simple. Grow your daily volume by inviting friends.",
    },
    "site_hero_title": {
        Language.fa: "کانفیگ آزمایشی رایگان، هر روز",
        Language.en: "A free trial config, every day",
    },
    "site_hero_sub": {
        Language.fa: "بدون ثبت‌نام و بدون ایمیل. کانفیگ امروزت را بگیر و با دعوت دوستان حجم روزانه‌ات را بیشتر کن.",
        Language.en: "No signup, no email. Grab today's config and grow your daily volume by inviting friends.",
    },
    # Web Push nudge copy — sent server-side (panel webhook / reconcile), localized per subscription.
    "site_push_expired_title": {
        Language.fa: "کانفیگ آزمایشی‌ات تمام شد",
        Language.en: "Your trial config ended",
    },
    "site_push_expired_body": {
        Language.fa: "دوباره سر بزن و کانفیگ رایگان امروزت را بگیر.",
        Language.en: "Come back and grab today's free config.",
    },
    "site_push_limited_title": {
        Language.fa: "حجم امروزت تمام شد",
        Language.en: "You're out of volume",
    },
    "site_push_limited_body": {
        Language.fa: "با دعوت دوستان حجم بیشتری بگیر تا همین کانفیگ دوباره فعال شود.",
        Language.en: "Invite friends to earn more volume and revive this same config.",
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
            landing_repo = SiteLandingPageRepository(session)
            for key, value in {**DEFAULT_SETTINGS, **DEFAULT_SITE_SETTINGS}.items():
                await settings_repo.add_default(key, value)
            for bodies_by_key in (DEFAULT_CONTENT, DEFAULT_SITE_CONTENT):
                for key, bodies in bodies_by_key.items():
                    for lang, body in bodies.items():
                        await content_repo.add_default(key, lang, body)
            for landing in DEFAULT_SITE_LANDINGS:
                await landing_repo.add_default(**landing)  # type: ignore[arg-type]
            await session.commit()
        logger.info(
            "seed: ensured %d settings (%d bot + %d site) + %d content keys + %d landings "
            "(defaults only, existing rows untouched)",
            len(DEFAULT_SETTINGS) + len(DEFAULT_SITE_SETTINGS),
            len(DEFAULT_SETTINGS),
            len(DEFAULT_SITE_SETTINGS),
            len(DEFAULT_CONTENT) + len(DEFAULT_SITE_CONTENT),
            len(DEFAULT_SITE_LANDINGS),
        )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
