"""Gozar v2 — Telegram trial-config bot package.

Import-clean by design: importing any module here has zero side effects
(no env reads, no DB/network, no destructive actions). All runtime wiring
happens inside the FastAPI lifespan, the arq worker ``run()``, or a CLI
``main()``.
"""

__version__ = "0.1.0"
