"""Seed default ``content`` + ``settings`` rows (idempotent).

Run: ``python -m gozar.seed``

Wired into the container entrypoint now so the boot sequence is stable forever;
it is a no-op until Phase 2 fills in the default copy and runtime values.
"""

from __future__ import annotations

import logging

from gozar.config.logging import configure_logging
from gozar.config.settings import get_settings

logger = logging.getLogger("gozar.seed")


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    # P2: open a DB session and upsert default `content` + `settings` rows (idempotent).
    logger.info("seed: no defaults to apply yet (Phase 0)")


if __name__ == "__main__":
    main()
