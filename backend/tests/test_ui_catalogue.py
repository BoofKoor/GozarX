"""The button catalogue stays in lockstep with the i18n label map and the screen set."""

from __future__ import annotations

from gozar.ui.catalogue import CATALOGUE, CRITICAL_KEYS, Screen
from gozar.ui.labels import _LABELS


def test_catalogue_keys_match_labels_minus_coming_soon() -> None:
    # Every editable button is a real i18n key; only `coming_soon` (not a button) is excluded.
    assert {e.key for e in CATALOGUE} == set(_LABELS) - {"coming_soon"}


def test_every_screen_has_entries() -> None:
    assert {e.screen for e in CATALOGUE} == set(Screen)


def test_no_duplicate_key_per_screen() -> None:
    seen: set[tuple[Screen, str]] = set()
    for e in CATALOGUE:
        slot = (e.screen, e.key)
        assert slot not in seen, f"duplicate placement {slot}"
        seen.add(slot)


def test_critical_keys_are_real_labels() -> None:
    assert CRITICAL_KEYS <= set(_LABELS)


def test_is_critical_matches_membership() -> None:
    for e in CATALOGUE:
        assert e.is_critical == (e.key in CRITICAL_KEYS)
