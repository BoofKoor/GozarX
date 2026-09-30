"""Bot buttons (auth-gated) — edit the in-code button catalogue via ``button_configs``.

Appearance (per-language label + visibility) and order (row/position) are edited separately so each
op preserves the other. Critical chrome (back/confirm/nav) can never be hidden — a 422 guards it.
Writes go through ``ButtonService`` (Redis-cached), so the bot picks them up on the next update.
Every mutation returns the full refreshed listing (grouped client-side by ``screen``).
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gozar.services.button_service import ButtonService, EditorButton
from gozar.ui.catalogue import CRITICAL_KEYS, Screen
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/buttons", tags=["buttons"])

# Bot API 9.4 inline-button colors; null = the app's default style.
_STYLES = frozenset({"primary", "success", "danger"})


def _service(request: Request, session: object) -> ButtonService:
    return ButtonService(session, request.app.state.redis)  # type: ignore[arg-type]


class ButtonOut(BaseModel):
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


class AppearancePatch(BaseModel):
    labels: dict[str, str] | None = None
    is_visible: bool = True
    style: str | None = None
    #: The screen the editor was opened on: visibility then applies there alone. Omitted, it is
    #: key-wide — every screen the key appears on.
    screen: str | None = None


class ReorderItem(BaseModel):
    key: str
    row_index: int = Field(ge=0, le=99)
    position: int = Field(ge=0, le=99)


class ReorderIn(BaseModel):
    items: list[ReorderItem]
    #: The screen being arranged. A key can sit on several (change_location is on three), and
    #: without this an order set on one screen applied to all of them.
    screen: str | None = None


_SCREENS = frozenset(s.value for s in Screen)


def _check_screen(screen: str | None) -> None:
    if screen is not None and screen not in _SCREENS:
        raise HTTPException(422, f"unknown screen: {screen}")


def _out(b: EditorButton) -> ButtonOut:
    return ButtonOut(**asdict(b))


@router.get("/", response_model=list[ButtonOut])
async def list_buttons(request: Request, session: DbSession, admin: AdminUser) -> list[ButtonOut]:
    return [_out(b) for b in await _service(request, session).list_for_editor()]


@router.put("/{key}", response_model=list[ButtonOut])
async def update_button(
    key: str, body: AppearancePatch, request: Request, session: DbSession, admin: AdminUser
) -> list[ButtonOut]:
    if key in CRITICAL_KEYS and not body.is_visible:
        raise HTTPException(422, "critical buttons cannot be hidden")
    if body.style is not None and body.style not in _STYLES:
        raise HTTPException(422, "style must be primary, success, danger, or null")
    _check_screen(body.screen)
    svc = _service(request, session)
    await svc.set_appearance(
        key, labels=body.labels, is_visible=body.is_visible, style=body.style, screen=body.screen
    )
    return [_out(b) for b in await svc.list_for_editor()]


@router.post("/{key}/reset", response_model=list[ButtonOut])
async def reset_button(
    key: str, request: Request, session: DbSession, admin: AdminUser
) -> list[ButtonOut]:
    svc = _service(request, session)
    await svc.reset(key)
    return [_out(b) for b in await svc.list_for_editor()]


@router.post("/reorder", response_model=list[ButtonOut])
async def reorder_buttons(
    body: ReorderIn, request: Request, session: DbSession, admin: AdminUser
) -> list[ButtonOut]:
    _check_screen(body.screen)
    svc = _service(request, session)
    await svc.reorder([(i.key, i.row_index, i.position) for i in body.items], screen=body.screen)
    return [_out(b) for b in await svc.list_for_editor()]
