from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from v3xctrl_control.message import Message

Address = tuple[str, int]


class MessageFromAddress(NamedTuple):
    message: Message
    address: Address
