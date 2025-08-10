from __future__ import annotations
from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from v3xctrl_control.message import Message

Address = tuple[str, int]


class MessageFromAddress(NamedTuple):
    message: Message
    address: Address
