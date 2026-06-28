"""Bot texts (auth-gated) — edit the per-language ``content`` table copy via ``ContentService``.

Lists every key (DB rows ∪ the seeded defaults, so a key shows even if a language row is missing),
its fa/en/ru body and the ``{token}`` placeholders it uses. A write upserts the row and invalidates
the bot's content cache. ``/preview`` renders a body against a sample for the editor's live preview.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from gozar.db.models.enums import Language
from gozar.db.repositories.content import ContentRepository
from gozar.seed import DEFAULT_CONTENT
from gozar.services.content import ContentService, render, sanitize_tokens
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/texts", tags=["texts"])

_TOKEN = re.compile(r"\{(\w+)\}")


class TextOut(BaseModel):
    key: str
    fa: str
    en: str
    ru: str
    placeholders: list[str]
    link_preview: bool


class TextPatch(BaseModel):
    fa: str | None = None
    en: str | None = None
    ru: str | None = None
    link_preview: bool = True


class PreviewIn(BaseModel):
    body: str
    sample: dict[str, str] = Field(default_factory=dict)


class PreviewOut(BaseModel):
    rendered: str
    missing_placeholders: list[str]


def _placeholders(*bodies: str) -> list[str]:
    seen: dict[str, None] = {}
    for body in bodies:
        for name in _TOKEN.findall(body):
            seen.setdefault(name, None)
    return list(seen)


async def _rows_by_key(repo: ContentRepository) -> dict[str, dict]:
    """``{key: {"bodies": {lang: body}, "link_preview": bool}}`` — the flag is per key."""
    out: dict[str, dict] = {}
    for row in await repo.all():
        entry = out.setdefault(row.key, {"bodies": {}, "link_preview": True})
        entry["bodies"][row.language.value] = row.body
        entry["link_preview"] = row.link_preview
    return out


def _text_out(key: str, entry: dict) -> TextOut:
    by_lang: dict[str, str] = entry.get("bodies", {})
    defaults = DEFAULT_CONTENT.get(key, {})
    fa = by_lang.get("fa", defaults.get(Language.fa, ""))
    en = by_lang.get("en", defaults.get(Language.en, ""))
    ru = by_lang.get("ru", defaults.get(Language.ru, ""))
    return TextOut(
        key=key,
        fa=fa,
        en=en,
        ru=ru,
        placeholders=_placeholders(fa, en, ru),
        link_preview=entry.get("link_preview", True),
    )


@router.get("/", response_model=list[TextOut])
async def list_texts(request: Request, session: DbSession, admin: AdminUser) -> list[TextOut]:
    by_key = await _rows_by_key(ContentRepository(session))
    keys = sorted(set(by_key) | set(DEFAULT_CONTENT))
    return [_text_out(key, by_key.get(key, {})) for key in keys]


@router.put("/{key}", response_model=TextOut)
async def update_text(
    key: str, body: TextPatch, request: Request, session: DbSession, admin: AdminUser
) -> TextOut:
    content = ContentService(session, request.app.state.redis)
    # The editor saves all three languages together, so the per-key link_preview lands on every row.
    # sanitize_tokens strips any stray bidi/zero-width marks an RTL edit slipped inside ``{token}``.
    for lang, text in ((Language.fa, body.fa), (Language.en, body.en), (Language.ru, body.ru)):
        if text is not None:
            await content.set(key, lang, sanitize_tokens(text), body.link_preview)
    by_key = await _rows_by_key(ContentRepository(session))
    return _text_out(key, by_key.get(key, {}))


@router.post("/preview", response_model=PreviewOut)
async def preview_text(body: PreviewIn, admin: AdminUser) -> PreviewOut:
    rendered = render(body.body, dict(body.sample))
    missing = [p for p in _placeholders(body.body) if p not in body.sample]
    return PreviewOut(rendered=rendered, missing_placeholders=missing)
