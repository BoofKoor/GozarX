"""Site-device repository — the only path to the ``site_devices`` table.

The site analogue of ``UserRepository``, keyed by the opaque device ``uuid`` (never a telegram id).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import Select

from gozar.config.reporting import DISPLAY_TZ
from gozar.db.handles import new_handle, normalize_handle
from gozar.db.models.site_claim import SiteClaim
from gozar.db.models.site_device import SiteDevice, SiteDeviceStatus
from gozar.db.models.site_device_day import SiteDeviceDay
from gozar.db.repositories.base import BaseRepository

# How stale a `last_seen_at` may be before the next request refreshes it. Coarse on purpose: the
# column feeds daily buckets, and an unthrottled write would land on every page load.
_SEEN_THROTTLE = timedelta(hours=1)


def _device_filter(
    stmt: Select, status: str | None, search: str | None, ip_bucket: str | None
) -> Select:
    """Admin device-list filters: status, an IP bucket (deep-linked from the anti-abuse panel), and
    a substring search over handle / uuid / panel username. Shared by the page and its count so the
    two can never disagree about how many rows match."""
    if status:
        stmt = stmt.where(SiteDevice.status == status)
    if ip_bucket:
        stmt = stmt.where(SiteDevice.ip_bucket == ip_bucket)
    if search and search.strip():
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                SiteDevice.handle.ilike(like),
                SiteDevice.uuid.ilike(like),
                SiteDevice.site_panel_username.ilike(like),
            )
        )
    return stmt


class SiteDeviceRepository(BaseRepository):
    async def get(self, uuid: str) -> SiteDevice | None:
        return await self.session.get(SiteDevice, uuid)

    async def get_by_handle(self, handle: str) -> SiteDevice | None:
        """Resolve a public handle (e.g. an incoming ``?ref=`` value) back to its device."""
        return await self.session.scalar(
            select(SiteDevice).where(SiteDevice.handle == normalize_handle(handle))
        )

    async def _unique_handle(self) -> str:
        """A fresh handle not already taken. The DB unique constraint is the real backstop; this
        just avoids the retry in the overwhelmingly common (collision-free) case."""
        for _ in range(8):
            candidate = new_handle()
            exists = await self.session.scalar(
                select(SiteDevice.uuid).where(SiteDevice.handle == candidate)
            )
            if exists is None:
                return candidate
        return new_handle()

    async def create(
        self,
        uuid: str,
        *,
        fingerprint_hash: str | None = None,
        ip_bucket: str | None = None,
        referred_by: str | None = None,
    ) -> SiteDevice:
        device = SiteDevice(
            uuid=uuid,
            handle=await self._unique_handle(),
            fingerprint_hash=fingerprint_hash,
            ip_bucket=ip_bucket,
            referred_by=referred_by,
        )
        self.session.add(device)
        await self.session.flush()
        return device

    async def get_or_create(
        self,
        uuid: str,
        *,
        fingerprint_hash: str | None = None,
        ip_bucket: str | None = None,
        referred_by: str | None = None,
    ) -> tuple[SiteDevice, bool]:
        """Return (device, created). ``created`` is True only when a new row was inserted."""
        device = await self.get(uuid)
        if device is not None:
            return device, False
        created = await self.create(
            uuid,
            fingerprint_hash=fingerprint_hash,
            ip_bucket=ip_bucket,
            referred_by=referred_by,
        )
        return created, True

    async def delete(self, device: SiteDevice) -> None:
        """Hard-delete a device row (the P6 reset). ``site_claims`` + ``site_rewards`` follow via
        their ``ON DELETE CASCADE`` foreign keys."""
        await self.session.delete(device)
        await self.session.flush()

    async def get_by_site_panel_username(self, username: str) -> SiteDevice | None:
        """Reverse lookup for the panel webhook: map a site panel username back to its device."""
        return await self.session.scalar(
            select(SiteDevice).where(SiteDevice.site_panel_username == username)
        )

    async def list_revoke_pending(self) -> list[tuple[str, str]]:
        """``(uuid, site_panel_username)`` for every BLOCKED device still holding a panel handle —
        the block could not reach the panel, so its trial works until the sweep deletes it."""
        rows = await self.session.execute(
            select(SiteDevice.uuid, SiteDevice.site_panel_username).where(
                SiteDevice.status == SiteDeviceStatus.blocked,
                SiteDevice.site_panel_username.is_not(None),
            )
        )
        return [(str(uuid), name) for uuid, name in rows.all() if name]

    async def list_active_with_panel(self) -> list[tuple[str, str]]:
        """``(uuid, site_panel_username)`` for every ``active_config`` device with a live panel
        account — the audience the site reconcile sweep (P7) probes for ended/limited trials."""
        rows = await self.session.execute(
            select(SiteDevice.uuid, SiteDevice.site_panel_username).where(
                SiteDevice.status == SiteDeviceStatus.active_config,
                SiteDevice.site_panel_username.is_not(None),
            )
        )
        return [(uuid, name) for uuid, name in rows.all() if name]

    async def count(self) -> int:
        """Total device identities ever minted — the site funnel's top ('visits')."""
        return int(await self.session.scalar(select(func.count()).select_from(SiteDevice)) or 0)

    async def count_by_status(self) -> dict[str, int]:
        """``{status: count}`` over all devices (available / active_config / blocked)."""
        rows = await self.session.execute(
            select(SiteDevice.status, func.count()).group_by(SiteDevice.status)
        )
        # getattr(...,"value",...) survives a future migration of `status` to a native enum
        # (str(EnumMember) → "SiteDeviceStatus.active_config" would silently zero the counts).
        return {getattr(status, "value", status): int(n) for status, n in rows.all()}

    # --- analytics (Phase B) ---------------------------------------------------------------------
    async def active_since(self, since: datetime) -> int:
        """Distinct devices that PROVISIONED at/after ``since`` — site DAU/WAU/MAU (excludes
        change-location re-picks so it measures returning devices, not link switches)."""
        return int(
            await self.session.scalar(
                select(func.count(func.distinct(SiteClaim.device_uuid))).where(
                    SiteClaim.created_at >= since, SiteClaim.is_change.is_(False)
                )
            )
            or 0
        )

    async def streak_distribution(self) -> dict[str, int]:
        """Histogram of the current daily-claim streak → ``{"0","1-2","3-6","7+"}`` → devices.
        Shows how far the streak incentive actually reaches."""
        bucket = case(
            (SiteDevice.streak_count == 0, "0"),
            (SiteDevice.streak_count <= 2, "1-2"),
            (SiteDevice.streak_count <= 6, "3-6"),
            else_="7+",
        ).label("bucket")
        rows = await self.session.execute(select(bucket, func.count()).group_by(bucket))
        return {str(b): int(n) for b, n in rows.all()}

    async def active_streak_count(self, min_days: int) -> int:
        """Devices currently on a qualifying streak (``streak_count >= min_days``) — how many are
        earning the streak reward right now."""
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(SiteDevice)
                .where(SiteDevice.streak_count >= max(min_days, 1))
            )
            or 0
        )

    async def top_ip_buckets(self, limit: int = 8, min_devices: int = 2) -> list[tuple[str, int]]:
        """IP buckets shared by ``>= min_devices`` devices → ``[(bucket, device_count), …]`` desc.
        A soft farming signal (many identities behind one IP) — never a hard block by itself."""
        rows = await self.session.execute(
            select(SiteDevice.ip_bucket, func.count().label("n"))
            .where(SiteDevice.ip_bucket.is_not(None))
            .group_by(SiteDevice.ip_bucket)
            .having(func.count() >= min_devices)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [(str(b), int(n)) for b, n in rows.all()]

    # --- visit tracking ---------------------------------------------------------------------------
    async def touch_seen(
        self, device: SiteDevice, *, throttle: timedelta = _SEEN_THROTTLE, minted: bool = False
    ) -> None:
        """Record that this device was just seen: ``last_seen_at``, and the local day it was seen.

        Called from the identity dependency, so it fires on every identity-bearing request — hence
        the throttle: an unconditional UPDATE would turn every page load into a row write. A new
        LOCAL day always writes, whatever the throttle says, so the day's ``site_device_days`` row
        (and its ``first_at``) is exact rather than up to an hour late — or missing entirely for a
        device that visited once just after midnight.

        ``minted`` is for a device created in this request: its ``last_seen_at`` comes from the
        column's server default, so the throttle alone would skip the visit that minted it.
        """
        now = datetime.now(UTC)
        today = now.astimezone(DISPLAY_TZ).date()
        last = device.last_seen_at
        if (
            not minted
            and last is not None
            and now - last < throttle
            and last.astimezone(DISPLAY_TZ).date() == today
        ):
            return
        device.last_seen_at = now
        # Flushed first: a device minted in this request must exist before a row can reference it.
        await self.session.flush()
        await self.session.execute(
            pg_insert(SiteDeviceDay)
            .values(device_uuid=device.uuid, day=today, first_at=now)
            .on_conflict_do_nothing(index_elements=[SiteDeviceDay.device_uuid, SiteDeviceDay.day])
        )

    async def count_seen_since(self, start: datetime) -> int:
        """Devices seen at/after ``start`` — a window that runs to NOW.

        ``last_seen_at`` answers this exactly (a device seen in the window has its latest visit in
        it), to the throttle's resolution — and exactly when ``start`` is a local midnight, since
        the first request of a day always writes. It can NOT answer a window that has ended: see
        ``count_visited_between``.
        """
        return int(
            await self.session.scalar(
                select(func.count()).select_from(SiteDevice).where(SiteDevice.last_seen_at >= start)
            )
            or 0
        )

    async def count_visited_between(self, start: datetime, end: datetime) -> int:
        """Devices seen in ``[start, end)``, from the per-day record — the only honest count of a
        window that has ENDED. ``last_seen_at`` is overwritten on every visit, so counting a past
        window from it counted only the devices that never came back.

        ``start`` must be a local midnight (every windowed caller's is); ``end`` may fall mid-day,
        because ``first_at`` says whether the device had already been seen by then.
        """
        return int(
            await self.session.scalar(
                select(func.count(func.distinct(SiteDeviceDay.device_uuid))).where(
                    SiteDeviceDay.first_at >= start, SiteDeviceDay.first_at < end
                )
            )
            or 0
        )

    async def count_new_between(self, start: datetime, end: datetime) -> int:
        """Devices whose identity was minted in ``[start, end)`` — first-time visitors."""
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(SiteDevice)
                .where(SiteDevice.created_at >= start, SiteDevice.created_at < end)
            )
            or 0
        )

    async def count_returning_since(self, start: datetime) -> int:
        """Devices seen at/after ``start`` that already existed BEFORE it — real returning visitors.
        This is the number that says whether the site keeps anyone, and nothing reported it."""
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(SiteDevice)
                .where(SiteDevice.last_seen_at >= start, SiteDevice.created_at < start)
            )
            or 0
        )

    async def count_returning_between(self, start: datetime, end: datetime) -> int:
        """``count_returning_since`` for a window that has ended, from the per-day record."""
        return int(
            await self.session.scalar(
                select(func.count(func.distinct(SiteDeviceDay.device_uuid)))
                .join(SiteDevice, SiteDevice.uuid == SiteDeviceDay.device_uuid)
                .where(
                    SiteDeviceDay.first_at >= start,
                    SiteDeviceDay.first_at < end,
                    SiteDevice.created_at < start,
                )
            )
            or 0
        )

    async def visits_recorded_since(self) -> datetime | None:
        """The first instant the per-day record holds, or None before the first visit is recorded.

        Visit history starts when the recorder shipped: a window before this has no visit data,
        which is a different sentence from "nobody visited".
        """
        return await self.session.scalar(select(func.min(SiteDeviceDay.first_at)))

    async def seen_daily(self, since: datetime) -> list[tuple[str, int]]:
        """Distinct devices seen per LOCAL day at/after ``since`` → ``[(day, devices), …]``.

        One row per device per day by construction, so a count of rows is a count of devices.
        """
        first_day = since.astimezone(DISPLAY_TZ).date()
        rows = await self.session.execute(
            select(SiteDeviceDay.day, func.count())
            .where(SiteDeviceDay.day >= first_day)
            .group_by(SiteDeviceDay.day)
            .order_by(SiteDeviceDay.day)
        )
        return [(d.isoformat(), int(n)) for d, n in rows.all()]

    async def active_config_split(self, trial_hours: int) -> tuple[int, int]:
        """``(live, stale)`` among devices whose status is ``active_config``.

        "Live" means the trial window hasn't elapsed yet (``last_claim_at + trial_hours > now``).
        The status column alone overstates it: it is healed only by the panel webhook or the
        15-minute reconcile sweep, and the sweep SKIPS a device whenever the panel is unreachable —
        so during an outage the KPI silently keeps counting dead trials as active. Reporting the
        stale count separately makes the reconcile lag visible instead of inflating the headline.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=max(trial_hours, 1))
        live = func.count().filter(SiteDevice.last_claim_at > cutoff)
        stale = func.count().filter(
            (SiteDevice.last_claim_at <= cutoff) | SiteDevice.last_claim_at.is_(None)
        )
        row = (
            await self.session.execute(
                select(live, stale)
                .select_from(SiteDevice)
                .where(SiteDevice.status == SiteDeviceStatus.active_config)
            )
        ).one()
        return int(row[0] or 0), int(row[1] or 0)

    # --- admin device browser -------------------------------------------------------------------
    async def list_page(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        search: str | None = None,
        ip_bucket: str | None = None,
    ) -> list[SiteDevice]:
        """A page of devices, newest first, with optional status / search / IP-bucket filters.

        ``uuid`` (PK) tiebreaks ``created_at``: two devices minted in the same second would
        otherwise be dropped or duplicated across pages by LIMIT/OFFSET.
        """
        stmt = _device_filter(select(SiteDevice), status, search, ip_bucket)
        stmt = stmt.order_by(SiteDevice.created_at.desc(), SiteDevice.uuid.desc())
        result = await self.session.scalars(stmt.limit(limit).offset(offset))
        return list(result.all())

    async def count_filtered(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        ip_bucket: str | None = None,
    ) -> int:
        stmt = _device_filter(
            select(func.count()).select_from(SiteDevice), status, search, ip_bucket
        )
        return int(await self.session.scalar(stmt) or 0)

    async def list_fingerprint_peers(
        self, fingerprint_hash: str | None, exclude_uuid: str, limit: int = 10
    ) -> list[SiteDevice]:
        """Other devices sharing this one's browser fingerprint — the concrete rows behind the
        anti-abuse panel's "N devices share a fingerprint" figure, which named none of them."""
        if not fingerprint_hash:
            return []
        result = await self.session.scalars(
            select(SiteDevice)
            .where(
                SiteDevice.fingerprint_hash == fingerprint_hash,
                SiteDevice.uuid != exclude_uuid,
            )
            .order_by(SiteDevice.created_at.desc())
            .limit(limit)
        )
        return list(result.all())

    async def count_referred_by(self, uuid: str) -> int:
        """Devices that arrived through this one's invite link. ``referral_count`` on the row is the
        REWARDED tally (capped); this is the raw one, so the two can be compared."""
        return int(
            await self.session.scalar(
                select(func.count()).select_from(SiteDevice).where(SiteDevice.referred_by == uuid)
            )
            or 0
        )

    async def shared_fingerprint_device_count(self) -> int:
        """Devices sharing a ``fingerprint_hash`` with at least one other device (soft multi-account
        signal) — the total size of all fingerprint groups larger than one."""
        groups = (
            select(func.count().label("n"))
            .select_from(SiteDevice)
            .where(SiteDevice.fingerprint_hash.is_not(None))
            .group_by(SiteDevice.fingerprint_hash)
            .having(func.count() >= 2)
            .subquery()
        )
        return int(await self.session.scalar(select(func.coalesce(func.sum(groups.c.n), 0))) or 0)
