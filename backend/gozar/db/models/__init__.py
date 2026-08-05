"""Model registry — importing this package registers every table on ``Base.metadata``.

``migrations/env.py`` imports this so Alembic autogenerate sees all tables.
"""

from gozar.db.models.broadcast_draft import BroadcastDraft
from gozar.db.models.broadcast_log import BroadcastLog, BroadcastStatus
from gozar.db.models.button_config import ButtonConfig
from gozar.db.models.config_log import ConfigLog
from gozar.db.models.content import Content
from gozar.db.models.enums import Language, UserStatus, language_enum, user_status_enum
from gozar.db.models.push_subscription import PushSubscription
from gozar.db.models.setting import Setting
from gozar.db.models.site_claim import SiteClaim
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.models.site_faq_item import FAQ_CATEGORIES, SiteFaqItem
from gozar.db.models.site_landing_page import SiteLandingPage
from gozar.db.models.site_message import SiteMessage
from gozar.db.models.site_push_log import SitePushLog, SitePushStatus
from gozar.db.models.site_reward import SiteReward, SiteRewardType
from gozar.db.models.usage_sample import UsageSample
from gozar.db.models.user import User

__all__ = [
    "FAQ_CATEGORIES",
    "BroadcastDraft",
    "BroadcastLog",
    "BroadcastStatus",
    "ButtonConfig",
    "ConfigLog",
    "Content",
    "Language",
    "PushSubscription",
    "Setting",
    "SiteClaim",
    "SiteDevice",
    "SiteDeviceStatus",
    "SiteFaqItem",
    "SiteLandingPage",
    "SiteMessage",
    "SitePushLog",
    "SitePushStatus",
    "SiteReward",
    "SiteRewardType",
    "UsageSample",
    "User",
    "UserStatus",
    "language_enum",
    "user_status_enum",
]
