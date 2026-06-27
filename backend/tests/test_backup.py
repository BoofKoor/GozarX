"""Nightly DB backup task.

Covers the argv/env construction (password kept out of argv), the channel-id coercion, the skip
guards, the gzip+send round-trip with a mocked ``pg_dump``, pg_dump-failure handling, and — when a
database and the ``pg_dump`` binary are both present — a real end-to-end dump round-trip.
"""

from __future__ import annotations

import gzip
import os
import shutil
from types import SimpleNamespace

import pytest

from gozar.worker.tasks import _backup_chat_id, _pg_dump_argv_env, backup_database

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def _settings(
    *,
    channel: str = "-1001234567890",
    database_url: str = "postgresql+asyncpg://u:secretpw@db:5432/gozar",
) -> SimpleNamespace:
    return SimpleNamespace(backup_channel_id=channel, database_url=database_url)


class _Bot:
    """Captures every ``send_document`` call so a test can inspect the uploaded bytes."""

    def __init__(self) -> None:
        self.docs: list[tuple[object, object, object]] = []

    async def send_document(
        self, chat_id: object, document: object, caption: object = None
    ) -> None:
        self.docs.append((chat_id, document, caption))


# ── argv / env helper ─────────────────────────────────────────────────────────────────────────
def test_pg_dump_argv_keeps_password_out_of_argv() -> None:
    argv, env = _pg_dump_argv_env("postgresql+asyncpg://gozar:s3cret@dbhost:5433/gozardb")
    assert argv[0] == "pg_dump"
    assert argv[argv.index("-h") + 1] == "dbhost"
    assert argv[argv.index("-p") + 1] == "5433"
    assert argv[argv.index("-U") + 1] == "gozar"
    assert argv[argv.index("-d") + 1] == "gozardb"
    assert "--no-owner" in argv and "--no-privileges" in argv and "-w" in argv
    assert env["PGPASSWORD"] == "s3cret"
    assert "s3cret" not in " ".join(argv)  # password NEVER leaks into argv


def test_pg_dump_argv_defaults_host_and_port() -> None:
    argv, env = _pg_dump_argv_env("postgresql+asyncpg:///justdb")
    assert argv[argv.index("-h") + 1] == "localhost"
    assert argv[argv.index("-p") + 1] == "5432"
    assert argv[argv.index("-d") + 1] == "justdb"
    assert env["PGPASSWORD"] == ""


def test_backup_chat_id_numeric_and_username() -> None:
    assert _backup_chat_id("-1001234567890") == -1001234567890
    assert _backup_chat_id("  42 ") == 42
    assert _backup_chat_id("@gozar_backups") == "@gozar_backups"


# ── skip guards (no send) ───────────────────────────────────────────────────────────────────────
async def test_backup_skips_without_channel(monkeypatch) -> None:
    monkeypatch.setattr("gozar.worker.tasks.get_settings", lambda: _settings(channel=""))
    bot = _Bot()
    await backup_database({"bot": bot})
    assert bot.docs == []


async def test_backup_skips_without_bot(monkeypatch) -> None:
    monkeypatch.setattr("gozar.worker.tasks.get_settings", lambda: _settings())
    await backup_database({"bot": None})  # must not raise


# ── mocked round-trip ───────────────────────────────────────────────────────────────────────────
async def test_backup_sends_gzipped_dump(monkeypatch) -> None:
    monkeypatch.setattr("gozar.worker.tasks.get_settings", lambda: _settings())
    sql = b"-- PostgreSQL database dump\nCREATE TABLE users (id bigint);\n"

    async def fake_run(argv: list[str], env: dict[str, str]) -> tuple[int, bytes, bytes]:
        return 0, sql, b""

    monkeypatch.setattr("gozar.worker.tasks._run_pg_dump", fake_run)
    bot = _Bot()
    await backup_database({"bot": bot})

    assert len(bot.docs) == 1
    chat, document, caption = bot.docs[0]
    assert chat == -1001234567890  # numeric channel id coerced to int
    assert document.filename.startswith("gozar-") and document.filename.endswith(".sql.gz")
    assert gzip.decompress(document.data) == sql  # the gz unpacks back to the exact dump
    assert "GozarX DB backup" in caption


async def test_backup_skips_send_on_pg_dump_failure(monkeypatch) -> None:
    monkeypatch.setattr("gozar.worker.tasks.get_settings", lambda: _settings())

    async def fake_run(argv: list[str], env: dict[str, str]) -> tuple[int, bytes, bytes]:
        return 1, b"", b"pg_dump: error: connection to server failed"

    monkeypatch.setattr("gozar.worker.tasks._run_pg_dump", fake_run)
    bot = _Bot()
    await backup_database({"bot": bot})
    assert bot.docs == []  # a non-zero pg_dump exit sends nothing


async def test_backup_swallows_pg_dump_missing(monkeypatch) -> None:
    monkeypatch.setattr("gozar.worker.tasks.get_settings", lambda: _settings())

    async def boom(argv: list[str], env: dict[str, str]) -> tuple[int, bytes, bytes]:
        raise FileNotFoundError("pg_dump")

    monkeypatch.setattr("gozar.worker.tasks._run_pg_dump", boom)
    bot = _Bot()
    await backup_database({"bot": bot})  # OSError is caught — never crashes the worker
    assert bot.docs == []


# ── real round-trip (DB + pg_dump both present) ─────────────────────────────────────────────────
@pytest.mark.skipif(
    not TEST_DATABASE_URL or not shutil.which("pg_dump"),
    reason="needs TEST_DATABASE_URL + pg_dump on PATH",
)
async def test_backup_real_pg_dump_roundtrip(monkeypatch) -> None:
    monkeypatch.setattr(
        "gozar.worker.tasks.get_settings",
        lambda: _settings(database_url=TEST_DATABASE_URL),
    )
    bot = _Bot()
    await backup_database({"bot": bot})

    assert len(bot.docs) == 1
    _chat, document, _caption = bot.docs[0]
    dump = gzip.decompress(document.data).decode("utf-8", "replace")
    assert "PostgreSQL database dump" in dump  # pg_dump always writes this header
