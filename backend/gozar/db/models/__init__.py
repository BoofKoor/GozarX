"""Model registry — importing this package registers every table on ``Base.metadata``.

``migrations/env.py`` imports this so Alembic autogenerate sees all tables.
"""

from gozar.db.models.button_config import ButtonConfig
from gozar.db.models.config_log import ConfigLog
from gozar.db.models.content import Content
from gozar.db.models.enums import Language, UserStatus, language_enum, user_status_enum
from gozar.db.models.setting import Setting
from gozar.db.models.user import User

__all__ = [
    "ButtonConfig",
    "ConfigLog",
    "Content",
    "Language",
    "Setting",
    "User",
    "UserStatus",
    "language_enum",
    "user_status_enum",
]
