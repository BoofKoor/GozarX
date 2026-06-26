"""Database enums (native PostgreSQL enum types).

One shared ``sa.Enum`` instance per type, bound to ``Base.metadata`` and referenced by every column
that uses it, so Alembic emits exactly one ``CREATE TYPE`` per enum (separate per-column instances
double-emit the type). ``values_callable`` persists the member *values* (``available``, ``fa`` …),
which also keeps a future ``ALTER TYPE language ADD VALUE 'ar'`` clean.
"""

from __future__ import annotations

import enum

import sqlalchemy as sa

from gozar.db.base import Base


class UserStatus(enum.StrEnum):
    available = "available"
    active_config = "active_config"
    banned = "banned"


class Language(enum.StrEnum):
    fa = "fa"
    en = "en"
    ru = "ru"


user_status_enum = sa.Enum(
    UserStatus,
    name="user_status",
    metadata=Base.metadata,
    values_callable=lambda e: [m.value for m in e],
)
language_enum = sa.Enum(
    Language,
    name="language",
    metadata=Base.metadata,
    values_callable=lambda e: [m.value for m in e],
)
