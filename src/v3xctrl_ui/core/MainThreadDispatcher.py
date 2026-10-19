from collections import deque
from collections.abc import Callable
from typing import Any


class MainThreadDispatcher:
    """Carries callbacks from background threads to the main loop.

    Network acknowledgements and connection tests arrive on threads of their
    own, while pygame font rendering and surface updates belong to the thread
    that owns the display. Work posted here runs on the next drain.
    """

    def __init__(self) -> None:
        self._pending: deque[tuple[Callable[..., None], tuple[Any, ...]]] = deque()

    def post(self, callback: Callable[..., None], *arguments: Any) -> None:
        self._pending.append((callback, arguments))

    def drain(self) -> None:
        """Run everything posted so far. Call this once per main loop iteration."""
        while self._pending:
            callback, arguments = self._pending.popleft()
            callback(*arguments)
