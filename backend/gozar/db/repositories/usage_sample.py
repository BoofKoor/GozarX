"""Usage-sample repository — the only path to ``usage_samples``.

The table stores the panel's cumulative counter verbatim; everything a chart wants is a difference,
and every difference is taken HERE so the reset rule lives in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, select

from gozar.config.reporting import DISPLAY_TZ_NAME
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

    async def daily(self, since: date) -> list[DayUsage]:
        """Per LOCAL day since ``since``: traffic carried, and the concurrency during it.

        Traffic is the difference between the LAST cumulative reading of each day and the last of
        the day before — not the difference between a day's first and last sample, which would drop
        everything carried between the final sample of one day and the first of the next.

        A negative difference means the counter reset; it is reported as 0 traffic and flagged. The
        alternative — a negative bar, or a silently absorbed jump — is either nonsense on the chart
        or a lie in the total.

        The FIRST day in the result has no predecessor to difference against, so it carries 0 bytes
        and is dropped by the caller rather than being shown as a day the service was idle.
        """
        day = func.date(func.timezone(DISPLAY_TZ_NAME, UsageSample.captured_at)).label("day")
        rows = (
            await self.session.execute(
                select(
                    day,
                    # The last cumulative reading of the day: max() is right for a monotonic
                    # counter and, unlike "order by captured_at desc limit 1", needs no window.
                    # A reset mid-day is caught at the NEXT boundary, which is where it shows.
                    func.max(UsageSample.total_bytes).label("cum"),
                    func.max(UsageSample.online_now).label("peak"),
                    func.avg(UsageSample.online_now).label("avg"),
                )
                .where(func.timezone(DISPLAY_TZ_NAME, UsageSample.captured_at) >= since)
                .group_by(day)
                .order_by(day)
            )
        ).all()

        out: list[DayUsage] = []
        previous: int | None = None
        for d, cum, peak, avg in rows:
            cum = int(cum or 0)
            delta = 0 if previous is None else cum - previous
            reset = delta < 0
            out.append(
                DayUsage(
                    day=d.isoformat(),
                    bytes=max(0, delta),
                    peak_online=int(peak or 0),
                    avg_online=int(round(float(avg or 0))),
                    counter_reset=reset,
                )
            )
            previous = cum
        return out

    async def traffic_between(self, start: datetime, end: datetime) -> int:
        """Bytes carried in a window, as last-reading-in minus last-reading-before.

        Anchored on the reading BEFORE the window rather than the first one inside it, so traffic
        carried between the last sample before the window and the first inside it is not lost. With
        no earlier reading (the window contains the very first sample) the window's own first
        reading is the baseline — the only honest choice, since nothing is known before it.

        Returns 0 rather than a negative when the counter reset inside the window: a reset makes the
        true figure unknowable, and an unknowable figure must not be reported as a loss.
        """
        before = await self.session.scalar(
            select(UsageSample.total_bytes)
            .where(UsageSample.captured_at < start)
            .order_by(UsageSample.captured_at.desc())
            .limit(1)
        )
        inside = (
            await self.session.execute(
                select(
                    func.min(UsageSample.total_bytes),
                    func.max(UsageSample.total_bytes),
                ).where(UsageSample.captured_at >= start, UsageSample.captured_at < end)
            )
        ).one()
        low, high = inside
        if high is None:
            return 0
        baseline = int(before) if before is not None else int(low or 0)
        return max(0, int(high) - baseline)

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
