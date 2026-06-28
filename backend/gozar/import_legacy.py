"""One-time import of the previous bot's users from its SQLite DB into the new Postgres ``users``.

Run: ``python -m gozar.import_legacy <sqlite_path> [--batch 2000] [--dry-run]``

Reads the legacy ``users`` table and upserts each row with ``ON CONFLICT (telegram_id) DO NOTHING``:
**non-clobbering** (a user who already started the new bot is left untouched) and **idempotent**
(safe to re-run). Everyone is imported as ``available`` — the old configs/squad are gone, so users
re-claim fresh, and the first broadcast prunes anyone who blocked the old bot. ``config_logs`` are
NOT imported (only users are needed to broadcast). Logging only — never prints secrets.

Server use: ``docker compose cp old.db <app>:/tmp/legacy.db`` then
``docker compose exec <app> python -m gozar.import_legacy /tmp/legacy.db`` (``--dry-run`` first).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from gozar.config.logging import configure_logging
from gozar.config.settings import get_settings
from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.db.session import create_engine, create_sessionmaker

logger = logging.getLogger("gozar.import_legacy")

_LANGS = {lang.value for lang in Language}  # {"fa", "en", "ru"}


def _parse_created(value: object) -> datetime:
    """Legacy ``created_at`` is ``'YYYY-MM-DD'`` text → midnight UTC; now() if missing/odd."""
    if isinstance(value, str) and value.strip():
        try:
            return datetime.strptime(value.strip()[:10], "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def _map_row(row: sqlite3.Row) -> dict | None:
    """Map one legacy row → a new ``users`` insert dict, or ``None`` to skip (bad telegram_id)."""
    try:
        tid = int(row["user_id"])
    except (TypeError, ValueError):
        return None
    if tid <= 0:
        return None
    try:
        referrals = max(int(row["referral_count"] or 0), 0)
    except (TypeError, ValueError):
        referrals = 0
    language = Language(row["user_lang"]) if row["user_lang"] in _LANGS else Language.fa
    return {
        "telegram_id": tid,
        "status": UserStatus.available,  # clean slate — old configs are gone
        "language": language,
        "referral_count": referrals,
        "reminder_enabled": (row["reminder_status"] or "").strip().lower() == "active",
        "panel_username": None,
        "referred_by": None,
        "created_at": _parse_created(row["created_at"]),
    }


def read_legacy_users(sqlite_path: str) -> list[dict]:
    """Read + map the legacy ``users`` table into new-schema insert dicts (skipping bad rows)."""
    con = sqlite3.connect(sqlite_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(
            "SELECT user_id, user_lang, referral_count, reminder_status, created_at FROM users"
        )
        return [m for m in (_map_row(r) for r in cur) if m is not None]
    finally:
        con.close()


async def upsert_users(session: AsyncSession, rows: list[dict], *, batch: int = 2000) -> int:
    """Bulk ``INSERT ... ON CONFLICT (telegram_id) DO NOTHING`` in batches; returns rows inserted.
    Does NOT commit — the caller owns the transaction."""
    inserted = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i : i + batch]
        stmt = pg_insert(User).values(chunk).on_conflict_do_nothing(index_elements=["telegram_id"])
        result = await session.execute(stmt)
        inserted += result.rowcount or 0
        logger.info("import_legacy: %d/%d processed", min(i + batch, len(rows)), len(rows))
    return inserted


async def _import(sqlite_path: str, batch: int, dry_run: bool) -> None:
    rows = read_legacy_users(sqlite_path)
    logger.info("import_legacy: read %d valid users from %s", len(rows), sqlite_path)
    if dry_run:
        logger.info("import_legacy: --dry-run — nothing written")
        return
    engine = create_engine(get_settings().database_url)
    sessionmaker = create_sessionmaker(engine)
    try:
        async with sessionmaker() as session:
            inserted = await upsert_users(session, rows, batch=batch)
            await session.commit()
    finally:
        await engine.dispose()
    logger.info(
        "import_legacy: done — %d inserted, %d skipped (already present)",
        inserted,
        len(rows) - inserted,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import legacy bot users (SQLite) into Postgres.")
    parser.add_argument("sqlite_path", help="path to the old bot's SQLite database file")
    parser.add_argument("--batch", type=int, default=2000, help="rows per insert batch")
    parser.add_argument("--dry-run", action="store_true", help="read + validate without writing")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    asyncio.run(_import(args.sqlite_path, max(args.batch, 1), args.dry_run))


if __name__ == "__main__":
    main()
