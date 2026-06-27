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
from gozar.services.content import ContentService, render
from gozar.web.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/texts", tags=["texts"])

_TOKEN = re.compile(r"\{(\w+)\}")


class TextOut(BaseModel):
    key: str
    fa: str
    en: str
    ru: str
    placeholders: list[str]


class TextPatch(BaseModel):
    fa: str | None = None
    en: str | None = None
    ru: str | None = None


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


async def _bodies_by_key(repo: ContentRepository) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in await repo.all():
        out.setdefault(row.key, {})[row.language.value] = row.body
    return out


def _text_out(key: str, by_lang: dict[str, str]) -> TextOut:
    defaults = DEFAULT_CONTENT.get(key, {})
    fa = by_lang.get("fa", defaults.get(Language.fa, ""))
    en = by_lang.get("en", defaults.get(Language.en, ""))
    ru = by_lang.get("ru", defaults.get(Language.ru, ""))
    return TextOut(key=key, fa=fa, en=en, ru=ru, placeholders=_placeholders(fa, en, ru))


@router.get("/", response_model=list[TextOut])
async def list_texts(request: Request, session: DbSession, admin: AdminUser) -> list[TextOut]:
    by_key = await _bodies_by_key(ContentRepository(session))
    keys = sorted(set(by_key) | set(DEFAULT_CONTENT))
    return [_text_out(key, by_key.get(key, {})) for key in keys]


@router.put("/{key}", response_model=TextOut)
async def update_text(
    key: str, body: TextPatch, request: Request, session: DbSession, admin: AdminUser
) -> TextOut:
    content = ContentService(session, request.app.state.redis)
    for lang, text in ((Language.fa, body.fa), (Language.en, body.en), (Language.ru, body.ru)):
        if text is not None:
            await content.set(key, lang, text)
    by_key = await _bodies_by_key(ContentRepository(session))
    return _text_out(key, by_key.get(key, {}))


@router.post("/preview", response_model=PreviewOut)
async def preview_text(body: PreviewIn, admin: AdminUser) -> PreviewOut:
    rendered = render(body.body, dict(body.sample))
    missing = [p for p in _placeholders(body.body) if p not in body.sample]
    return PreviewOut(rendered=rendered, missing_placeholders=missing)
