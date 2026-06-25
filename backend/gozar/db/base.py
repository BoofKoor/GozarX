"""SQLAlchemy declarative base.

Models (Phase 1) subclass ``Base``; alembic's ``env.py`` imports
``Base.metadata`` as its autogenerate target. Defined in Phase 0 so the
migration harness imports cleanly even before any models exist.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
