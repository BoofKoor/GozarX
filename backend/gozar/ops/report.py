"""Progress reporting: the engine announces its plan and every step's outcome.

The worker renders it as one live-edited console message (``worker/ops``); tests read the steps.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from gozar.ops.errors import RemoteError

PENDING, RUNNING, OK, WARN, FAIL, SKIP = "pending", "running", "ok", "warn", "fail", "skip"
ICONS = {PENDING: "◻️", RUNNING: "⏳", OK: "✅", WARN: "⚠️", FAIL: "❌", SKIP: "➖"}


@dataclass
class StepState:
    key: str
    title: str
    status: str = PENDING
    note: str = ""
    started: float | None = None
    ended: float | None = None
    detail: str = ""  # raw output for failures

    def elapsed(self) -> float | None:
        if self.started is None:
            return None
        return (self.ended or time.monotonic()) - self.started


class Reporter:
    """Base reporter. Subclasses override `changed()` to render."""

    def __init__(self) -> None:
        self.steps: list[StepState] = []
        self.header: str = ""
        self.footer: str = ""
        self.debug_lines: list[str] = []
        self.context: dict = {}  # e.g. {"name": "tb2"} once allocated (for cleanup after a failure)

    # --- called by the engine ---------------------------------------------------------
    def debug(self, line: str) -> None:
        self.debug_lines.append(f"{time.strftime('%H:%M:%S')} {line}")

    async def plan(self, steps: list[tuple[str, str]], header: str = "") -> None:
        """The steps still to come. Steps already finished stay on top (a login before the work),
        so one message tells the whole job."""
        done = [s for s in self.steps if s.status not in (PENDING, RUNNING)]
        keys = {s.key for s in done}
        self.steps = done + [StepState(k, t) for k, t in steps if k not in keys]
        if header:
            self.header = header
        await self.changed()

    def _get(self, key: str, title: str | None = None) -> StepState:
        for s in self.steps:
            if s.key == key:
                if title:
                    s.title = title
                return s
        s = StepState(key, title or key)
        self.steps.append(s)
        return s

    async def set_header(self, header: str) -> None:
        self.header = header
        await self.changed()

    async def set_footer(self, footer: str) -> None:
        self.footer = footer
        await self.changed()

    async def skip(self, key: str, note: str = "") -> None:
        s = self._get(key)
        s.status, s.note = SKIP, note
        await self.changed()

    def stage(self, key: str, title: str | None = None) -> Stage:
        return Stage(self, self._get(key, title))

    async def changed(self) -> None:  # pragma: no cover - overridden
        pass

    # --- rendering helpers ------------------------------------------------------------
    def failed_step(self) -> StepState | None:
        return next((s for s in self.steps if s.status == FAIL), None)

    def render_lines(self) -> list[str]:
        out = []
        for s in self.steps:
            line = f"{ICONS[s.status]} {s.title}"
            el = s.elapsed()
            if s.status == RUNNING and el is not None and el >= 3:
                line += f" … {int(el)}ث"
            if s.note:
                line += f" — {s.note}"
            out.append(line)
        return out


class Stage:
    """`async with reporter.stage(key) as st:` marks a step running, then ok/warn/fail."""

    def __init__(self, rep: Reporter, step: StepState):
        self.rep = rep
        self.step = step
        self._warnings: list[str] = []

    async def note(self, text: str) -> None:
        self.step.note = text
        await self.rep.changed()

    def warn(self, text: str) -> None:
        self._warnings.append(text)

    async def __aenter__(self) -> Stage:
        self.step.status = RUNNING
        self.step.started = time.monotonic()
        self.step.note = ""
        await self.rep.changed()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self.step.ended = time.monotonic()
        if exc is None:
            if self._warnings:
                self.step.status = WARN
                self.step.note = "؛ ".join(
                    ([self.step.note] if self.step.note else []) + self._warnings
                )
            else:
                self.step.status = OK
        else:
            self.step.status = FAIL
            if isinstance(exc, RemoteError):
                self.step.note = exc.message
                self.step.detail = exc.detail
            else:
                self.step.note = f"خطای داخلی: {exc!r}"
            self.rep.debug(f"STEP FAILED {self.step.key}: {self.step.note}\n{self.step.detail}")
        await self.rep.changed()
        return False  # never swallow
