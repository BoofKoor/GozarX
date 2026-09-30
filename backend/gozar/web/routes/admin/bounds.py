"""The economy numbers' valid ranges — ONE definition for all four writers.

The bot's settings PUT floored its numbers and both wizards took anything: a negative daily volume
made the panel reject every trial it was asked to create, a trial long enough to overflow a
datetime turned every claim into a 500, and a daily volume of 0 is "unlimited" to Remnawave. The
forms already refused most of this client-side; the server did not, so anything that bypassed the
form (a stale tab, a script) went straight into the live economy. Out of range is now a 422 naming
the field, on the wizards and the settings pages alike.

The ceilings are generous on purpose — they stop nonsense, not operators: a year-long trial, a
terabyte a day, a hundred thousand rewarded invites.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

_MB_PER_TB = 1024 * 1024

#: At least an hour (0 is no trial at all); at most a year.
TrialHours = Annotated[int, Field(ge=1, le=24 * 365)]
#: At least 1 MB: Remnawave reads a traffic limit of 0 as UNLIMITED.
DailyLimitMb = Annotated[int, Field(ge=1, le=_MB_PER_TB)]
#: A reward may be switched off (0), never negative.
RewardMb = Annotated[int, Field(ge=0, le=_MB_PER_TB)]
#: 0 rewards no invite at all (the quota is ``min(referrals, cap)``).
RewardLimit = Annotated[int, Field(ge=0, le=100_000)]
#: The bot's location keyboard; Telegram draws a hundred buttons at most, fifty stay usable.
ConfigsPerPage = Annotated[int, Field(ge=1, le=50)]
#: 0 turns the streak bonus off.
StreakDays = Annotated[int, Field(ge=0, le=365)]
