from typing import Protocol, TypeVar
from v3xctrl_helper import Address

from .message import Message

T = TypeVar("T", bound=Message, contravariant=True)


class Handler(Protocol[T]):
    def __call__(self, msg: T, addr: Address, /) -> None:
        pass
