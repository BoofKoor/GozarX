"""Phase E's data migration (``5b7e2c9d4a61``) and the defaults it moves in step with.

A migration's text is frozen at the moment it was written, while the seed keeps being edited; if
the two drifted, a fresh install (seeded) and an upgraded one (migrated) would show different
questions. And the copy rows it blanks are only safe to blank while their old text is no longer
the code's default — otherwise "use the site's copy" would put the same claim straight back.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from gozar.db.models.enums import Language
from gozar.seed_faq import DEFAULT_SITE_FAQ
from gozar.services.site_copy_keys import SITE_COPY_DEFAULTS

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "5b7e2c9d4a61_site_phase_e_copy.py"
)


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("phase_e_copy", _MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_migration_adds_exactly_questions_the_seed_has() -> None:
    seeded = {(i["locale"], i["category"], i["question"], i["answer"]) for i in DEFAULT_SITE_FAQ}
    added = _migration().FAQ_ADDED
    assert len(added) == 8
    assert set(added) <= seeded
    # four per locale, so neither language's FAQ gains questions the other lacks
    assert sorted(row[0] for row in added) == ["en"] * 4 + ["fa"] * 4


def test_a_blanked_copy_row_no_longer_matches_its_default() -> None:
    for key, lang, old in _migration()._COPY:
        design_key = key.removeprefix("site_copy_")
        assert SITE_COPY_DEFAULTS[design_key][Language(lang)] != old
