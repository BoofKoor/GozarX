"""Repositories — the only path to the database. One AsyncSession per update (Phase 3)."""

from gozar.db.repositories.base import BaseRepository
from gozar.db.repositories.config_log import ConfigLogRepository
from gozar.db.repositories.content import ContentRepository
from gozar.db.repositories.settings import SettingsRepository
from gozar.db.repositories.site_claim import SiteClaimRepository
from gozar.db.repositories.site_device import SiteDeviceRepository
from gozar.db.repositories.site_message import SiteMessageRepository
from gozar.db.repositories.site_reward import SiteRewardRepository
from gozar.db.repositories.user import UserRepository

__all__ = [
    "BaseRepository",
    "ConfigLogRepository",
    "ContentRepository",
    "SettingsRepository",
    "SiteClaimRepository",
    "SiteDeviceRepository",
    "SiteMessageRepository",
    "SiteRewardRepository",
    "UserRepository",
]
