"""Neutral UI layer: button labels + the keyboard catalogue + the override renderer.

Depends only on ``db.models.enums``, so it can be imported **downward** by ``web/``, ``bot/`` AND
``services/`` without breaking the one-way import rule (delivery → services → infra). The bot's
keyboards consume it; ``ButtonService`` (in services/) overlays it with DB-backed overrides.
"""
