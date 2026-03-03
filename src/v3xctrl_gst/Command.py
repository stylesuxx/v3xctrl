import contextlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ActionType(StrEnum):
    STOP = "stop"
    LIST = "list"
    GET = "get"
    SET = "set"
    RECORDING = "recording"
    STATS = "stats"


class RecordingAction(StrEnum):
    START = "start"
    STOP = "stop"


class CommandValidationError(Exception):
    """Raised when a command fails validation."""

    pass


@dataclass
class Command:
    """Represents a control command."""

    action: ActionType
    element: str | None = None
    property: str | None = None
    value: Any | None = None
    properties: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, ActionType):
            try:
                self.action = ActionType(self.action)
            except ValueError as err:
                raise CommandValidationError(f"Unknown action: {self.action}") from err

        if self.action == ActionType.RECORDING and isinstance(self.value, str):
            with contextlib.suppress(ValueError):
                self.value = RecordingAction(self.value)

    def validate(self) -> None:
        """
        Validate command structure.

        Raises:
            CommandValidationError: If command is invalid
        """
        if not isinstance(self.action, ActionType):
            raise CommandValidationError(f"Unknown action: {self.action}")

        if self.action == ActionType.STOP or self.action == ActionType.STATS:
            return

        if self.action == ActionType.RECORDING:
            if not self.value:
                raise CommandValidationError("Missing value parameter")

            return

        if not self.element:
            raise CommandValidationError("Missing element parameter")

        if self.action == ActionType.LIST:
            return

        if not self.property:
            raise CommandValidationError("Missing property parameter")

        if self.action == ActionType.SET and self.value is None:
            raise CommandValidationError("Missing value")
