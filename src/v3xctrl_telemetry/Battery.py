from v3xctrl_telemetry import INA
from v3xctrl_helper import clamp


class Battery:
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

        self.voltage = 0
        self.average_voltage = 0
        self.warning = False
        self.percentage = 100
        self.cell_count = self._guess_cell_count()

    def _guess_cell_count(self) -> int:
        """
        Guess cell count based on average cell voltage - minimum 1 to prevent
        division by zero
        """
        voltage = self._sensor.get_bus_voltage()
        average_cell_voltage = (self.min_cell_voltage + self.max_cell_voltage) / 2

        return max(round(voltage / average_cell_voltage), 1)

    def update(self) -> None:
        self.voltage = self._sensor.get_bus_voltage()
        self.average_voltage = round(self.voltage / self.cell_count)

        # Calculate percentage
        min_voltage = self.min_cell_voltage * self.cell_count
        max_voltage = self.max_cell_voltage * self.cell_count
        percentage = round((self.voltage - min_voltage) / (max_voltage - min_voltage) * 100)
        percentage = clamp(percentage, 0, 100)
        self.percentage = percentage

        # Check warning states
        self.warning = (self.voltage / self.cell_count) <= self.warn_cell_voltage

    def get_volts(self) -> float:
        return self.voltage / 1000
