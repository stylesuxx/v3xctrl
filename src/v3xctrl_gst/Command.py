from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, get_args


ActionType = Literal['stop', 'list', 'get', 'set', 'recording', 'stats']
valid_actions = get_args(ActionType)


class CommandValidationError(Exception):
    """Raised when a command fails validation."""
    pass


@dataclass
class Command:
    """Represents a control command."""
    action: ActionType
    element: Optional[str] = None
    property: Optional[str] = None
    value: Optional[Any] = None
    properties: Optional[Dict[str, Any]] = None

    def validate(self) -> None:
        """
        Validate command structure.

        Raises:
            CommandValidationError: If command is invalid
        """
        if self.action not in valid_actions:
            raise CommandValidationError(f'Unknown action: {self.action}')

        if (
            self.action == 'stop' or
            self.action == 'stats'
        ):
            return

        if self.action == 'recording':
            if not self.value:
                raise CommandValidationError('Missing value parameter')

            return

        if not self.element:
            raise CommandValidationError('Missing element parameter')

        if self.action == 'list':
            return

        if not self.property:
            raise CommandValidationError('Missing property parameter')

        if self.action == 'set' and self.value is None:
            raise CommandValidationError('Missing value')
