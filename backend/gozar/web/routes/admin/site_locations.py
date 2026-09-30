"""Shared location validation for the website admin routes.

The settings PUT already refused location names the configured squad doesn't serve; the first-run
wizard stored whatever it was given. That gap is the v1 index-mismatch lesson in a new shape: a
typo (or a name left over from another squad) was persisted, offered to visitors on the public
picker, and picking it handed them a config for a different country. Both writers now come here.

Validation is best-effort BY DESIGN: with no squad configured, or the panel unreachable, we store
what the admin typed rather than blocking them during an outage.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status

from gozar.remnawave import RemnawaveError
from gozar.remnawave.links import normalize_remark

logger = logging.getLogger("gozar.web.admin.site_locations")


async def known_squad_locations(request: Request, squad: str | None) -> list[str] | None:
    """The squad's remark NAMES, or ``None`` when they can't be established right now.

    ``None`` means "unverifiable" (no squad set, or the panel is down) — never "empty". An empty
    LIST, by contrast, is a real answer meaning the squad matched no enabled host.
    """
    if not squad:
        return None
    try:
        return await request.app.state.panel.squad_location_names(squad)
    except RemnawaveError:
        logger.warning("locations not validated — panel unreachable")
        return None


def unknown_names(wanted: list[str], known: list[str]) -> list[str]:
    """Names in ``wanted`` the squad doesn't serve, matched by NORMALISED remark name (never by
    index — the v1 lesson). Pure, so it's unit-testable without a panel."""
    allowed = {normalize_remark(name) for name in known}
    return [name for name in wanted if normalize_remark(name) not in allowed]


async def reject_unknown_locations(request: Request, squad: str | None, wanted: list[str]) -> None:
    """400 on any requested name the squad doesn't serve. No-op when unverifiable."""
    if not wanted:
        return
    known = await known_squad_locations(request, squad)
    if not known:  # None = unverifiable, [] = nothing to check against
        return
    unknown = unknown_names(wanted, known)
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"not served by the squad: {', '.join(unknown)} — available: {', '.join(known)}",
        )


async def reject_unknown_squad(request: Request, squad: str) -> None:
    """400 when the panel answers and the squad is not one of its squads. No-op when unverifiable.

    A squad deleted in the panel used to be kept: the wizard's select showed the first live squad
    while the form still held the dead uuid, and ``known_squad_locations`` reads an unknown squad
    as "nothing to check" — so the save went through and the service could no longer provision.
    """
    try:
        squads = await request.app.state.panel.list_internal_squads()
    except RemnawaveError:
        logger.warning("squad not validated — panel unreachable")
        return
    if squads and all(s.uuid != squad for s in squads):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "that squad no longer exists in the panel — pick one of its current squads",
        )


async def offered_locations(request: Request, squad: str | None, stored: list[str]) -> list[str]:
    """What the picker offers for a stored list: the list itself, or — when it is empty, which
    means "all of them" — the squad's live names (``[]`` when those can't be read right now)."""
    if stored:
        return stored
    return await known_squad_locations(request, squad) or []


def reject_popular_outside_list(popular: str, locations: list[str]) -> None:
    """400 when the starred "popular" location isn't one of the offered ones.

    An empty string clears the flag and is always allowed. Without this the panel could star a
    location the picker doesn't even show — the ⭐ then pointed at nothing.
    """
    if not popular.strip():
        return
    if not locations:
        return  # no allowlist configured yet — nothing to contradict
    if unknown_names([popular], locations):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"popular location '{popular}' is not in the offered locations: {', '.join(locations)}",
        )
