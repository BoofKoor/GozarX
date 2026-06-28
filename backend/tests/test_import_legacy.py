"""Legacy import: the SQLite read+map (no DB) and the DB-gated on-conflict upsert.

A tiny temp SQLite mirrors the old bot's ``users`` schema so the import is exercised without the
real 50k-row file. The upsert tests use the ``session`` fixture (skipped without TEST_DATABASE_URL).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC

from sqlalchemy import func, select

from gozar.db.models.enums import Language, UserStatus
from gozar.db.models.user import User
from gozar.import_legacy import read_legacy_users, upsert_users

_COLS = "user_id, user_status, referral_count, sub_name, created_at, user_lang, reminder_status"


def _make_legacy_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE users (user_id INTEGER PRIMARY KEY, user_status TEXT, referral_count INTEGER,"
        " sub_name TEXT, created_at TEXT, user_lang TEXT, reminder_status TEXT)"
    )
    con.executemany(
        f"INSERT INTO users ({_COLS}) VALUES (?,?,?,?,?,?,?)",
        [
            (111, "active", 5, "x", "2025-08-31", "fa", "active"),
            (222, "deactive", 0, "y", "2026-04-14", "en", "inactive"),
            (333, "active", 2, "z", "bad-date", "ru", "active"),
            (0, "active", 0, None, "2025-01-01", "fa", "active"),  # bad telegram_id -> skipped
            (444, "active", 0, None, "2025-01-01", "xx", "active"),  # unknown lang -> fa
        ],
    )
    con.commit()
    con.close()


def test_read_legacy_users_maps_and_skips(tmp_path) -> None:
    db = str(tmp_path / "old.db")
    _make_legacy_db(db)
    by_id = {r["telegram_id"]: r for r in read_legacy_users(db)}
    assert set(by_id) == {111, 222, 333, 444}  # user_id 0 is skipped
    assert by_id[111]["language"] is Language.fa and by_id[111]["referral_count"] == 5
    assert by_id[111]["reminder_enabled"] is True and by_id[111]["status"] is UserStatus.available
    assert by_id[222]["language"] is Language.en and by_id[222]["reminder_enabled"] is False
    assert by_id[333]["language"] is Language.ru  # 'bad-date' falls back to now()
    assert by_id[444]["language"] is Language.fa  # unknown 'xx' -> fa
    assert by_id[111]["created_at"].year == 2025 and by_id[111]["created_at"].tzinfo is UTC


async def test_upsert_users_inserts_and_is_non_clobbering(session, tmp_path) -> None:
    db = str(tmp_path / "old.db")
    _make_legacy_db(db)
    rows = read_legacy_users(db)
    # a user who already started the NEW bot must NOT be overwritten by the import
    session.add(
        User(
            telegram_id=111,
            language=Language.en,
            referral_count=99,
            status=UserStatus.active_config,
        )
    )
    await session.commit()

    inserted = await upsert_users(session, rows, batch=2)  # batch < len -> exercises chunking
    await session.commit()
    assert inserted == 3  # 222, 333, 444 (111 already present -> skipped by ON CONFLICT)
    assert await session.scalar(select(func.count()).select_from(User)) == 4

    session.expire_all()
    kept = await session.get(User, 111)
    assert kept.language is Language.en and kept.referral_count == 99  # untouched

    again = await upsert_users(session, rows, batch=2)  # idempotent
    await session.commit()
    assert again == 0
