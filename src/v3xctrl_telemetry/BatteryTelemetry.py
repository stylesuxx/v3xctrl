from dataclasses import dataclass
from v3xctrl_telemetry import INA
from v3xctrl_helper import clamp


@dataclass
class BatteryState:
    """Battery telemetry state."""
    voltage: int = 0
    average_voltage: int = 0
    percentage: int = 100
    warning: bool = False
    cell_count: int = 1


class BatteryTelemetry:
    def __init__(
        self,
        min_cell_voltage: int = 3500,
        max_cell_voltage: int = 4200,
        warn_cell_voltage: int = 3700,
        address: int = 0x40,
        bus: int = 1
    ) -> None:
        self._sensor = INA(address, bus)
        self.min_cell_voltage = min_cell_voltage
        self.max_cell_voltage = max_cell_voltage
        self.warn_cell_voltage = warn_cell_voltage

        self._state = BatteryState(
            voltage=0,
            average_voltage=0,
            percentage=100,
            warning=False,
            cell_count=self._guess_cell_count()
        )

    def _guess_cell_count(self) -> int:
        """
        Guess cell count based on average cell voltage - minimum 1 to prevent
        division by zero
        """
        voltage = self._sensor.get_bus_voltage()
        average_cell_voltage = (self.min_cell_voltage + self.max_cell_voltage) / 2

        return max(round(voltage / average_cell_voltage), 1)

    def update(self) -> None:
        """Update battery telemetry from INA sensor."""
        self._state.voltage = self._sensor.get_bus_voltage()
        self._state.average_voltage = round(self._state.voltage / self._state.cell_count)

        # Calculate percentage
        min_voltage = self.min_cell_voltage * self._state.cell_count
        max_voltage = self.max_cell_voltage * self._state.cell_count
        percentage = round((self._state.voltage - min_voltage) / (max_voltage - min_voltage) * 100)
        percentage = clamp(percentage, 0, 100)
        self._state.percentage = percentage

        # Check warning states
        self._state.warning = (self._state.voltage / self._state.cell_count) <= self.warn_cell_voltage

    def get_state(self) -> BatteryState:
        return self._state
