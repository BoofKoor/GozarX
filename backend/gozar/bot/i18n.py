"""Back-compat shim — button labels moved to ``gozar.ui.labels``.

The label map now lives in the neutral ``gozar.ui`` package so ``services/`` (e.g. the
``ButtonService``) can import the defaults without importing delivery code. Existing
``from gozar.bot.i18n import t, LANGUAGE_NAMES`` imports keep working through this re-export.
"""

from __future__ import annotations

from gozar.ui.labels import _LABELS, LANGUAGE_NAMES, t

__all__ = ["LANGUAGE_NAMES", "_LABELS", "t"]
