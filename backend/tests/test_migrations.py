"""Migration chain sanity + the data migrations' own statements."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.script import ScriptDirectory

from gozar.db.repositories.settings import SettingsRepository

BACKEND = Path(__file__).resolve().parents[1]


def _migration(revision: str):
    path = next((BACKEND / "migrations" / "versions").glob(f"{revision}_*.py"))
    spec = importlib.util.spec_from_file_location(f"migration_{revision}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_chain_has_one_head() -> None:
    # Two heads make `alembic upgrade head` refuse to run, and the entrypoint runs it on every boot.
    assert len(ScriptDirectory(str(BACKEND / "migrations")).get_heads()) == 1


async def test_site_locations_reset_offers_every_host_and_leaves_the_bot_alone(session) -> None:
    repo = SettingsRepository(session)
    await repo.set("site_locations", '["Germany", "🇩🇪 DE"]')  # the wizard's day-one snapshot
    await repo.set("locations", '["Germany"]')  # the bot's list: honoured all along, so kept
    await session.execute(_migration("c7f62cc5a366").RESET)
    session.expire_all()
    assert await repo.get("site_locations") == "[]"
    assert await repo.get("locations") == '["Germany"]'
