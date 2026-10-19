"""Protocols for the modules a settings change reaches."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from v3xctrl_ui.core.Settings import Settings


@runtime_checkable
class SettingsSubscriber(Protocol):
    """A module that takes new settings into use.

    Implementations re-apply unconditionally and are safe to call with settings
    they have already seen.
    """

    def apply_settings(self, settings: "Settings") -> None: ...


class NetworkRestarter(Protocol):
    """The network stack, seen from the settings side.

    A restart runs in the background because tearing down and rebinding sockets
    blocks. Completion is polled from the main loop, so that new settings are
    applied on the thread that owns the display.
    """

    def restart(self, settings: "Settings") -> None:
        """Begin restarting the network stack for the new settings."""
        ...

    def is_restart_complete(self) -> bool:
        """True once a restart begun by restart() has finished."""
        ...

    def acknowledge_restart(self) -> None:
        """Clear the completion flag so the next restart can signal again."""
        ...

    def wait_for_restart(self, timeout: float) -> bool:
        """Block until a running restart finishes. True if it finished in time."""
        ...
