"""Phase 1 model/metadata sanity — runs without a database."""

from __future__ import annotations

from gozar.db import models  # noqa: F401  (importing registers all tables on Base.metadata)
from gozar.db.base import Base
from gozar.db.models.enums import Language, UserStatus


def _table(name: str):
    return Base.metadata.tables[name]


def test_all_tables_registered() -> None:
    assert set(Base.metadata.tables) == {
        # bot
        "users",
        "config_logs",
        "content",
        "settings",
        "button_configs",
        "broadcast_logs",
        # website (separate product, shared infra)
        "site_devices",
        "site_claims",
        "site_rewards",
        "push_subscriptions",
        "site_messages",
        "site_landing_pages",
        "site_push_logs",
        "site_faq_items",
    }


def test_users_columns() -> None:
    users = _table("users")
    assert set(users.columns.keys()) == {
        "telegram_id",
        "status",
        "language",
        "referral_count",
        "panel_username",
        "reminder_enabled",
        "referred_by",
        "created_at",
        "last_claim_at",
    }
    assert users.c.telegram_id.primary_key is True
    assert users.c.telegram_id.autoincrement is False
    assert users.c.panel_username.nullable is True
    assert users.c.referred_by.nullable is True
    assert users.c.referred_by.index is True
    assert users.c.last_claim_at.nullable is True


def test_enum_values() -> None:
    assert [s.value for s in UserStatus] == ["available", "active_config", "banned"]
    assert [lang.value for lang in Language] == ["fa", "en", "ru"]


def test_language_enum_is_one_shared_type() -> None:
    # Same native type object on users + content -> a single CREATE TYPE language.
    assert _table("users").c.language.type is _table("content").c.language.type


def test_content_unique_key_language() -> None:
    uniques = [
        c for c in _table("content").constraints if c.__class__.__name__ == "UniqueConstraint"
    ]
    assert any({col.name for col in u.columns} == {"key", "language"} for u in uniques)


def test_config_logs_fk_cascade() -> None:
    fks = list(_table("config_logs").c.user_id.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "users"
    assert fks[0].ondelete == "CASCADE"
