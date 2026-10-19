"""What a screen is drawn with: the 🎨 switches plus what Telegram taught us, as one snapshot.

``services/look.LookService`` builds it per screen — the switches live in the ``settings`` table and
the learned state in Redis, so the app and the worker draw alike. Everything here is pure: a
lookup never calls anything.

Premium emoji depend on the bot OWNER's subscription, not on who is reading, so there is one state
for the whole bot. When Telegram refuses or drops our custom emoji the bot draws plain emoji for a
day (``blocked``) and tries again after that, or at once from 🎨.
"""

from __future__ import annotations

from dataclasses import dataclass

from gozar.ui.icons import FLAGS, TEXT, button_id, flag_code, named_icon, norm


@dataclass(frozen=True, slots=True)
class Look:
    #: 🎨 switch: draw premium icons (when Telegram allows them).
    premium: bool = True
    #: 🎨 switch: structured console screens as rich messages (tables, folding sections).
    rich: bool = True
    #: Learned: Telegram refused or dropped our custom emoji (the owner has no Premium) — plain
    #: emoji until the block expires.
    blocked: bool = False
    #: Learned: ids Telegram no longer knows (the daily ``getCustomEmojiStickers`` check).
    missing: frozenset[str] = frozenset()

    @property
    def icons_on(self) -> bool:
        return self.premium and not self.blocked

    def usable(self, eid: str | None) -> str | None:
        return eid if eid and eid not in self.missing else None

    def text_icon(self, emoji: str, after: str = "") -> str | None:
        """The id for an emoji found in a text (``after`` = the text right after it, which a mark of
        ``icons.NAMED`` reads for its logo), or None."""
        code = flag_code(emoji)
        if code:
            return self.usable(FLAGS.get(code))
        e = norm(emoji)
        return self.usable(TEXT.get(e) or named_icon(e, after))

    def button_icon(self, emoji: str, coloured_button: bool = False) -> str | None:
        code = flag_code(emoji)
        if code:
            return self.usable(FLAGS.get(code))
        return self.usable(button_id(emoji, coloured_button))

    def flag_id(self, code: str | None) -> str | None:
        """The premium flag of a country (ISO alpha-2), or None while icons are off."""
        if not code or not self.icons_on:
            return None
        return self.usable(FLAGS.get(code.upper()))


#: Plain emoji and regular messages — what ``/simple`` switches to, and what tests draw with.
PLAIN = Look(premium=False, rich=False)
