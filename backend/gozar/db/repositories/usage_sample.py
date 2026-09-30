"""Usage-sample repository — the only path to ``usage_samples``.

The table stores the panel's cumulative counter verbatim; everything a chart wants is a difference,
and every difference is taken HERE so the reset rule lives in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy import func, select

from gozar.config.reporting import DISPLAY_TZ
from gozar.db.models.usage_sample import UsageSample
from gozar.db.repositories.base import BaseRepository


@dataclass(slots=True)
class DayUsage:
    """One LOCAL day of carried traffic, plus the concurrency seen during it."""

    day: str
    bytes: int
    peak_online: int
    avg_online: int
    #: The lifetime counter went DOWN across this day's boundary — a panel restart, a node removed
    #: and re-added, or an admin resetting traffic. The delta is reported as 0 rather than as a
    #: negative, and this flag is why the chart can say so instead of just drawing a gap.
    counter_reset: bool


@dataclass(slots=True)
class TrafficWindow:
    """Traffic carried in a window, and whether the counter reset inside it (then the figure is a
    floor: what crossed the reset itself cannot be known)."""

    bytes: int
    counter_reset: bool


class UsageSampleRepository(BaseRepository):
    async def record(
        self,
        *,
        total_bytes: int,
        online_now: int,
        nodes_online: int,
        mem_used: int,
        mem_total: int,
    ) -> UsageSample:
        row = UsageSample(
            total_bytes=total_bytes,
            online_now=online_now,
            nodes_online=nodes_online,
            mem_used=mem_used,
            mem_total=mem_total,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def first_captured_at(self) -> datetime | None:
        """When recording began. The empty state needs it: "no data for this range" and "we have
        not been recording that long" are different answers and deserve different sentences."""
        return await self.session.scalar(select(func.min(UsageSample.captured_at)))

    async def sample_count(self) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(UsageSample)) or 0)

    async def _reading_before(self, at: datetime) -> int | None:
        return await self.session.scalar(
            select(UsageSample.total_bytes)
            .where(UsageSample.captured_at < at)
            .order_by(UsageSample.captured_at.desc())
            .limit(1)
        )

    async def daily(self, since: date) -> list[DayUsage]:
        """Per LOCAL day from ``since``: traffic carried, and the concurrency during it.

        A day's traffic is the sum of the POSITIVE steps between consecutive readings whose later
        reading falls in that day, starting from the last reading before ``since`` — so nothing
        carried between two days falls down the gap between them.

        A step DOWN means the counter reset (a panel restart, a node removed and re-added, a manual
        traffic reset). That step counts as 0 — what was carried across it is unknowable — and flags
        the day it happened on. Differencing daily maxima instead, as this used to, gave the reset
        day only its pre-reset traffic and pinned the flag, and a zero, on the day AFTER it.

        With no reading before ``since`` (recording began inside the range), the first day has no
        baseline for its first step, so it is partial: it is left out rather than drawn as a
        quiet day.
        """
        start = datetime.combine(since, time(0), tzinfo=DISPLAY_TZ)
        baseline = await self._reading_before(start)
        rows = (
            await self.session.execute(
                select(UsageSample.captured_at, UsageSample.total_bytes, UsageSample.online_now)
                .where(UsageSample.captured_at >= start)
                .order_by(UsageSample.captured_at)
            )
        ).all()

        days: dict[str, dict] = {}
        previous = baseline
        first_day = None
        for captured_at, total, online in rows:
            key = captured_at.astimezone(DISPLAY_TZ).date().isoformat()
            if first_day is None:
                first_day = key
            entry = days.setdefault(key, {"bytes": 0, "online": [], "reset": False})
            entry["online"].append(int(online or 0))
            total = int(total)
            if previous is not None:
                step = total - previous
                if step < 0:
                    entry["reset"] = True
                else:
                    entry["bytes"] += step
            previous = total

        out: list[DayUsage] = []
        for key, entry in days.items():
            if key == first_day and baseline is None:
                continue  # partial: its first step had nothing to be measured from
            online = entry["online"]
            out.append(
                DayUsage(
                    day=key,
                    bytes=entry["bytes"],
                    peak_online=max(online),
                    avg_online=int(round(sum(online) / len(online))),
                    counter_reset=entry["reset"],
                )
            )
        return out

    async def traffic_between(self, start: datetime, end: datetime) -> TrafficWindow:
        """Bytes carried in ``[start, end)``: the sum of positive steps between consecutive
        readings, anchored on the reading BEFORE the window (so the traffic between the last reading
        before it and the first inside is not lost).

        With no earlier reading, the window's own first reading is the baseline — nothing is known
        before it. A step DOWN is a counter reset: it counts 0 and sets ``counter_reset``. This used
        to be "highest reading inside minus the one before", which a reset mid-window cut short:
        everything carried after the reset was lost, silently (200 reported for 850 carried).
        """
        previous = await self._reading_before(start)
        rows = await self.session.scalars(
            select(UsageSample.total_bytes)
            .where(UsageSample.captured_at >= start, UsageSample.captured_at < end)
            .order_by(UsageSample.captured_at)
        )
        carried = 0
        reset = False
        for total in rows:
            total = int(total)
            if previous is not None:
                step = total - previous
                if step < 0:
                    reset = True
                else:
                    carried += step
            previous = total
        return TrafficWindow(bytes=carried, counter_reset=reset)

    async def peak_online_between(self, start: datetime, end: datetime) -> int:
        return int(
            await self.session.scalar(
                select(func.max(UsageSample.online_now)).where(
                    UsageSample.captured_at >= start, UsageSample.captured_at < end
                )
            )
            or 0
        )

    async def latest(self) -> UsageSample | None:
        return await self.session.scalar(
            select(UsageSample).order_by(UsageSample.captured_at.desc()).limit(1)
        )
