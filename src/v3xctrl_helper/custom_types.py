from __future__ import annotations
from typing import Callable, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from v3xctrl_control.Message import Message
    from v3xctrl_control.State import State

Address = tuple[str, int]


class MessageHandler(TypedDict):
    type: type
    func: Callable[[Message], None]


class StateHandler(TypedDict):
    state: State
    func: Callable[[], None]
