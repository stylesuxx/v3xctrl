from enum import IntEnum, Enum
from smbus3 import SMBus


class INARegister(IntEnum):
    CONFIG = 0x00
    SHUNT_VOLTAGE = 0x01
    BUS_VOLTAGE = 0x02
    POWER = 0x03
    CURRENT = 0x04
    CALIBRATION = 0x05


class INAUnits(Enum):
    BUS_VOLTAGE = 1.25
    SHUNT_VOLTAGE = 2.5


class INA:
    """
    This should work with all kinds of different INA chips.

    Th following have been tested:
    - INA231
    """

    def __init__(self, address: int = 0x40, bus: int = 1) -> None:
        """
        Initalize the INA object.

        Default address is 0x40. Can be verified with:
        > sudo i2cdetect -y 1

        Sets the calibration to the default value (1000). If you use a different
        shunt then default, call set_calibration with the appropriate
        calibration value.
        """
        self.address = address
        self.bus = SMBus(bus)

        self.set_calibration()

    def _swap_bytes(self, value: int) -> int:
        # INA chips return registers in little-endian format
        return ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)

    def _read_register(self, register: INARegister) -> int:
        # Reads a 16-bit word and swaps byte order
        raw = self.bus.read_word_data(self.address, register)

        return self._swap_bytes(raw)

    def _write_register(self, register: INARegister, value: int) -> None:
        # Writes a 16-bit word with correct byte order
        swapped = self._swap_bytes(value)
        self.bus.write_word_data(self.address, register, swapped)

    def set_calibration(
        self,
        r_shunt_ohms: float = 0.01,
        max_expected_current_A: float = 3.2
    ) -> None:
        """
        Set calibration register based on shunt resistor and expected max
        current.

        Defaults:
        - r_shunt_ohms: 0.01 Ω (10 mΩ)
        - max_expected_current_A: 3.2 A

        This sets:
        - current_LSB: scaled to max current with 15-bit margin
        - calibration register
        - derived power_LSB
        """

        # Leave margin: use 15-bit range, not full 16-bit
        self.current_LSB = max_expected_current_A / 32767
        self.current_LSB *= 1e6

        # From datasheet: CAL = 0.00512 / (current_LSB * R_shunt)
        current_LSB_A = self.current_LSB / 1e6
        calibration = int(0.00512 / (current_LSB_A * r_shunt_ohms))

        # µW/bit
        self.power_LSB = 25 * self.current_LSB

        self._write_register(INARegister.CALIBRATION, calibration)

    def get_bus_Voltage(self) -> int:
        # Returns bus voltage in mV
        raw = self._read_register(INARegister.BUS_VOLTAGE)

        return int(raw * INAUnits.BUS_VOLTAGE.value)

    def get_shunt_Voltage(self) -> int:
        # Returns shunt voltage in uV
        raw = self._read_register(INARegister.SHUNT_VOLTAGE)

        return int(raw * INAUnits.SHUNT_VOLTAGE.value)

    def get_current(self) -> int:
        # Returns current in uA
        raw = self._read_register(INARegister.CURRENT)

        return int(raw * self.current_LSB)

    def get_power(self) -> int:
        # Returns power in uW
        raw = self._read_register(INARegister.POWER)

        return int(raw * self.power_LSB)
