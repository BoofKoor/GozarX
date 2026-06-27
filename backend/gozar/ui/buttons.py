"""Override-aware keyboard rendering.

``render_rows`` is the single builder every keyboard in ``bot/keyboards.py`` calls. A keyboard
declares its layout as ``list[list[ButtonSpec]]`` (outer index = default row, inner = default
position); ``render_rows`` applies the DB overrides (label / visibility / order) carried by a
``ButtonOverrides`` snapshot and emits the ``InlineKeyboardMarkup``.

With ``buttons=None`` (no snapshot) the output is byte-identical to the original hand-written
``.adjust(...)`` layouts — that back-compat is what ``tests/test_keyboards.py`` pins.

Rules:
- **Label** — every keyed cell uses ``snapshot.label(key, lang)`` or falls back to ``t(key, lang)``.
- **Visibility** — non-critical keyed cells may be hidden; critical and raw (data-driven) cells
  are always shown.
- **Order** — non-critical keyed cells may move via ``row``/``position`` overrides; critical and raw
  cells stay at their structural slot. Rows are regrouped by effective row, sorted by position, and
  **re-packed densely** so a hidden or moved button never leaves a gap.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from gozar.db.models.enums import Language
from gozar.ui.catalogue import CRITICAL_KEYS
from gozar.ui.labels import t


@dataclass(frozen=True, slots=True)
class ButtonSpec:
    """One cell in a keyboard's default layout.

    Keyed cells (``key`` set) resolve their label/visibility/order from the catalogue + overrides.
    Raw cells (``key`` None, ``label`` given) are data-driven (location remarks, language names) and
    bypass override resolution. Exactly one of ``callback_data`` / ``url`` is set.
    """

    key: str | None = None
    label: str | None = None
    callback_data: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class Override:
    """A single button's DB override (built by ``ButtonService`` from a ``button_configs`` row)."""

    labels: Mapping[str, str] = field(default_factory=dict)
    is_visible: bool = True
    row: int | None = None
    position: int | None = None


class ButtonOverrides:
    """Immutable per-update snapshot of all button overrides, keyed by i18n key."""

    __slots__ = ("_by_key",)

    def __init__(self, by_key: Mapping[str, Override]) -> None:
        self._by_key = dict(by_key)

    def label(self, key: str, lang: Language) -> str | None:
        ov = self._by_key.get(key)
        return None if ov is None else ov.labels.get(lang.value)

    def is_visible(self, key: str) -> bool:
        ov = self._by_key.get(key)
        return True if ov is None else ov.is_visible

    def row(self, key: str) -> int | None:
        ov = self._by_key.get(key)
        return None if ov is None else ov.row

    def position(self, key: str) -> int | None:
        ov = self._by_key.get(key)
        return None if ov is None else ov.position


EMPTY_OVERRIDES = ButtonOverrides({})


def render_rows(
    lang: Language,
    structure: Sequence[Sequence[ButtonSpec]],
    buttons: ButtonOverrides | None = None,
) -> InlineKeyboardMarkup:
    ov = buttons if buttons is not None else EMPTY_OVERRIDES

    # (eff_row, eff_pos, stable_order, text, callback_data, url)
    collected: list[tuple[int, int, int, str, str | None, str | None]] = []
    order = 0
    for d_row, row in enumerate(structure):
        for d_pos, spec in enumerate(row):
            if spec.key is None:  # raw data-driven cell — never overridden, never hidden
                collected.append(
                    (d_row, d_pos, order, spec.label or "", spec.callback_data, spec.url)
                )
                order += 1
                continue

            text = ov.label(spec.key, lang) or t(spec.key, lang)
            if spec.key in CRITICAL_KEYS:  # pinned: always visible, never reordered
                collected.append((d_row, d_pos, order, text, spec.callback_data, spec.url))
                order += 1
                continue

            if not ov.is_visible(spec.key):
                continue
            eff_row = ov.row(spec.key)
            eff_row = d_row if eff_row is None else eff_row
            eff_pos = ov.position(spec.key)
            eff_pos = d_pos if eff_pos is None else eff_pos
            collected.append((eff_row, eff_pos, order, text, spec.callback_data, spec.url))
            order += 1

    collected.sort(key=lambda c: (c[0], c[1], c[2]))

    builder = InlineKeyboardBuilder()
    sizes: list[int] = []
    prev_row: int | None = None
    count = 0
    for eff_row, _pos, _order, text, callback_data, url in collected:
        if prev_row is not None and eff_row != prev_row:
            sizes.append(count)
            count = 0
        prev_row = eff_row
        if url is not None:
            builder.button(text=text, url=url)
        else:
            builder.button(text=text, callback_data=callback_data)
        count += 1
    if count:
        sizes.append(count)
    if sizes:
        builder.adjust(*sizes)
    return builder.as_markup()
