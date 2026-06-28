"""Button-config service — Redis-cached overlay of the in-code button catalogue (Phase 7c).

Loads all ``button_configs`` rows once (cached as one JSON blob), exposing them as a
``ButtonOverrides`` snapshot the keyboards consume, plus admin edit/reset and an editor-facing
merged listing. Lives in services/ so it imports only ui/ + db/ + cache/ — never delivery code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from gozar.cache.redis import BUTTON_CONFIGS_KEY, CACHE_TTL
from gozar.db.models.enums import Language
from gozar.db.repositories.button_config import ButtonConfigRepository
from gozar.ui.buttons import ButtonOverrides, Override
from gozar.ui.catalogue import CATALOGUE, CRITICAL_KEYS
from gozar.ui.labels import t


@dataclass(frozen=True, slots=True)
class EditorButton:
    """One catalogue entry merged with its override — the admin Buttons-editor row shape."""

    key: str
    screen: str
    is_critical: bool
    is_visible: bool
    default_row: int
    default_position: int
    effective_row: int
    effective_position: int
    default_label: dict[str, str]
    effective_label: dict[str, str]
    style: str | None
    customized: bool


class ButtonService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._repo = ButtonConfigRepository(session)
        self._redis = redis

    async def _raw(self) -> dict[str, dict]:
        """All overrides as ``{key: {labels, is_visible, row_index, position}}`` — Redis-cached."""
        cached = await self._redis.get(BUTTON_CONFIGS_KEY)
        if cached is not None:
            return json.loads(cached)
        rows = await self._repo.all()
        raw = {
            r.key: {
                "labels": r.labels or {},
                "is_visible": r.is_visible,
                "row_index": r.row_index,
                "position": r.position,
                "style": r.style,
            }
            for r in rows
        }
        await self._redis.set(BUTTON_CONFIGS_KEY, json.dumps(raw), ex=CACHE_TTL)
        return raw

    async def snapshot(self) -> ButtonOverrides:
        """The immutable per-update overlay the bot's keyboards render through."""
        raw = await self._raw()
        by_key = {
            key: Override(
                labels=ov.get("labels") or {},
                is_visible=ov.get("is_visible", True),
                row=ov.get("row_index"),
                position=ov.get("position"),
                style=ov.get("style"),
            )
            for key, ov in raw.items()
        }
        return ButtonOverrides(by_key)

    async def set(
        self,
        key: str,
        *,
        labels: dict[str, str] | None,
        is_visible: bool,
        row_index: int | None,
        position: int | None,
        style: str | None = None,
    ) -> None:
        await self._repo.upsert(
            key,
            labels=labels,
            is_visible=is_visible,
            row_index=row_index,
            position=position,
            style=style,
        )
        await self.invalidate()

    async def set_appearance(
        self, key: str, *, labels: dict[str, str] | None, is_visible: bool, style: str | None = None
    ) -> None:
        """Edit label + visibility + color (the Buttons-editor modal), preserving any order."""
        existing = await self._repo.get(key)
        await self._repo.upsert(
            key,
            labels=labels,
            is_visible=is_visible,
            row_index=existing.row_index if existing else None,
            position=existing.position if existing else None,
            style=style,
        )
        await self.invalidate()

    async def reorder(self, items: list[tuple[str, int, int]]) -> None:
        """Bulk set row/position (drag-drop), preserving each key's label + visibility."""
        existing = {r.key: r for r in await self._repo.all()}
        for key, row_index, position in items:
            if key in CRITICAL_KEYS:  # criticals are pinned to their structural slot — never moved
                continue
            cur = existing.get(key)
            await self._repo.upsert(
                key,
                labels=cur.labels if cur else None,
                is_visible=cur.is_visible if cur else True,
                row_index=row_index,
                position=position,
                style=cur.style if cur else None,
            )
        await self.invalidate()

    async def reset(self, key: str) -> None:
        """Drop the override → the button reverts to its code/catalogue default."""
        await self._repo.delete(key)
        await self.invalidate()

    async def invalidate(self) -> None:
        await self._redis.delete(BUTTON_CONFIGS_KEY)

    async def list_for_editor(self) -> list[EditorButton]:
        """Every catalogue entry merged with its override (default + effective) for the API."""
        rows = {r.key: r for r in await self._repo.all()}
        out: list[EditorButton] = []
        for entry in CATALOGUE:
            row = rows.get(entry.key)
            default_label = {lang.value: t(entry.key, lang) for lang in Language}
            override_labels = (row.labels or {}) if row else {}
            effective_label = {
                code: override_labels.get(code) or default_label[code] for code in default_label
            }
            is_visible = row.is_visible if row else True
            if entry.is_critical:  # render_rows pins criticals; show them at their structural slot
                eff_row, eff_pos = entry.default_row, entry.default_position
            else:
                eff_row = entry.default_row if not row or row.row_index is None else row.row_index
                eff_pos = (
                    entry.default_position if not row or row.position is None else row.position
                )
            customized = bool(
                row
                and (
                    override_labels
                    or not row.is_visible
                    or row.row_index is not None
                    or row.position is not None
                    or row.style is not None
                )
            )
            out.append(
                EditorButton(
                    key=entry.key,
                    screen=entry.screen.value,
                    is_critical=entry.is_critical,
                    is_visible=is_visible,
                    default_row=entry.default_row,
                    default_position=entry.default_position,
                    effective_row=eff_row,
                    effective_position=eff_pos,
                    default_label=default_label,
                    effective_label=effective_label,
                    style=row.style if row else None,
                    customized=customized,
                )
            )
        return out
