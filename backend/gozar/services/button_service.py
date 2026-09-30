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

from gozar.cache.redis import BUTTON_CONFIGS_KEY, CACHE_TTL, defer_cache_invalidation
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
                "screens": r.screens or {},
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
                screens=ov.get("screens") or {},
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
        existing = await self._repo.get(key)
        await self._repo.upsert(
            key,
            labels=labels,
            is_visible=is_visible,
            row_index=row_index,
            position=position,
            style=style,
            screens=existing.screens if existing else None,
        )
        await self.invalidate()

    async def set_appearance(
        self,
        key: str,
        *,
        labels: dict[str, str] | None,
        is_visible: bool,
        style: str | None = None,
        screen: str | None = None,
    ) -> None:
        """Edit label + visibility + color (the Buttons-editor modal), preserving any order.

        With ``screen``, the visibility applies to THAT screen only; labels and colour are always
        key-wide (a button's name is its name everywhere). Without it, the key-wide visibility.
        """
        existing = await self._repo.get(key)
        screens = dict(existing.screens or {}) if existing else {}
        key_visible = existing.is_visible if existing else True
        if screen is None:
            key_visible = is_visible
        else:
            screens[screen] = {**screens.get(screen, {}), "visible": is_visible}
        await self._repo.upsert(
            key,
            labels=labels,
            is_visible=key_visible,
            row_index=existing.row_index if existing else None,
            position=existing.position if existing else None,
            style=style,
            screens=screens or None,
        )
        await self.invalidate()

    async def reorder(self, items: list[tuple[str, int, int]], screen: str | None = None) -> None:
        """Bulk set row/position (drag-drop), preserving each key's label + visibility.

        With ``screen``, the order is recorded for that screen alone — a key on several screens used
        to move on all of them at once. Without it (the old API), key-wide.
        """
        existing = {r.key: r for r in await self._repo.all()}
        for key, row_index, position in items:
            if key in CRITICAL_KEYS:  # criticals are pinned to their structural slot — never moved
                continue
            cur = existing.get(key)
            screens = dict(cur.screens or {}) if cur else {}
            key_row = cur.row_index if cur else None
            key_pos = cur.position if cur else None
            if screen is None:
                key_row, key_pos = row_index, position
            else:
                screens[screen] = {
                    **screens.get(screen, {}),
                    "row": row_index,
                    "position": position,
                }
            await self._repo.upsert(
                key,
                labels=cur.labels if cur else None,
                is_visible=cur.is_visible if cur else True,
                row_index=key_row,
                position=key_pos,
                style=cur.style if cur else None,
                screens=screens or None,
            )
        await self.invalidate()

    async def reset(self, key: str) -> None:
        """Drop the override → the button reverts to its code/catalogue default."""
        await self._repo.delete(key)
        await self.invalidate()

    async def invalidate(self) -> None:
        # Now AND after the commit. Deleted only now, a bot update landing between this and the
        # commit re-read the OLD rows and cached them for the full TTL: an edit took up to five
        # minutes to reach the bot while the panel already showed it saved.
        await self._redis.delete(BUTTON_CONFIGS_KEY)
        defer_cache_invalidation(self._repo.session, BUTTON_CONFIGS_KEY)

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
            # The SAME resolution the bot's renderer applies for this screen: per-screen entry,
            # else the key-wide value, else the catalogue default.
            per = ((row.screens or {}) if row else {}).get(entry.screen.value, {})
            key_row = row.row_index if row else None
            key_pos = row.position if row else None
            key_visible = row.is_visible if row else True
            is_visible = key_visible if per.get("visible") is None else bool(per["visible"])
            if entry.is_critical:  # render_rows pins criticals; show them at their structural slot
                eff_row, eff_pos = entry.default_row, entry.default_position
            else:
                r = per.get("row") if per.get("row") is not None else key_row
                p = per.get("position") if per.get("position") is not None else key_pos
                eff_row = entry.default_row if r is None else int(r)
                eff_pos = entry.default_position if p is None else int(p)
            customized = bool(
                row
                and (
                    override_labels
                    or not is_visible
                    or key_row is not None
                    or key_pos is not None
                    or per.get("row") is not None
                    or per.get("position") is not None
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
