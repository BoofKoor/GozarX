"""Worker ``reset_all_active`` — the admin's bulk "reset daily consumption".

The panel keys ``/api/users/{…}/actions/reset-traffic`` by the user's ``uuid`` on Remnawave 2.x and
by the numeric ``id`` on 3.x, which dropped the uuid. Keyed on the uuid alone, every user on a 3.x
panel was counted as skipped and nobody's traffic was reset. DB-gated (real sessions via
``db_sessions``) with a fake panel.
"""

from __future__ import annotations

from gozar.db.models.enums import UserStatus
from gozar.db.models.user import User
from gozar.remnawave.schemas import PanelUser
from gozar.worker.tasks import reset_all_active


class FakePanel:
    """``get_user`` answers from a username map (absent = a 404); records every reset key."""

    def __init__(self, records: dict[str, PanelUser]) -> None:
        self._records = records
        self.reset: list[str] = []

    async def get_user(self, username: str) -> PanelUser | None:
        return self._records.get(username)

    async def reset_user_traffic(self, ref: str) -> bool:
        self.reset.append(ref)
        return True


async def test_reset_all_active_keys_each_user_the_way_its_panel_does(db_sessions) -> None:
    async with db_sessions() as session:
        session.add_all(
            [
                User(telegram_id=1, status=UserStatus.active_config, panel_username="g1"),
                User(telegram_id=2, status=UserStatus.active_config, panel_username="g2"),
                User(telegram_id=3, status=UserStatus.active_config, panel_username="g3"),
                User(telegram_id=4, status=UserStatus.available),  # holds no config
            ]
        )
        await session.commit()

    panel = FakePanel(
        {
            "g1": PanelUser(uuid="uuid-1", id=1, username="g1"),  # a 2.x record: uuid wins
            "g2": PanelUser(id=2, username="g2"),  # a 3.x record: only the numeric id
            # g3 is gone from the panel (404) — skipped, never a reset of nothing
        }
    )
    await reset_all_active({"sessionmaker": db_sessions, "panel": panel, "bot": None}, 99)

    assert sorted(panel.reset) == ["2", "uuid-1"]
