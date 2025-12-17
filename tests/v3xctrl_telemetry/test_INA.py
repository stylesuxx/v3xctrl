"""Tests for INA sensor interface."""
import unittest
from unittest.mock import Mock, patch, MagicMock

from v3xctrl_telemetry.INA import INA, INARegister, INAUnits


class TestINA(unittest.TestCase):
    """Test INA sensor interface with mocked SMBus."""

    def setUp(self):
        """Set up test fixtures with mocked SMBus."""
        self.mock_smbus_patcher = patch('v3xctrl_telemetry.INA.SMBus')
        self.mock_smbus_class = self.mock_smbus_patcher.start()
        self.mock_bus = MagicMock()
        self.mock_smbus_class.return_value = self.mock_bus

    def tearDown(self):
        """Clean up patches."""
        self.mock_smbus_patcher.stop()

    def test_initialization_default_values(self):
        """Test INA initializes with default address and bus."""
        ina = INA()

        assert ina.address == 0x40
        self.mock_smbus_class.assert_called_once_with(1)
        # Should call set_calibration during init
        assert self.mock_bus.write_word_data.called

    def test_initialization_custom_values(self):
        """Test INA initializes with custom address and bus."""
        ina = INA(address=0x41, bus=0)

        assert ina.address == 0x41
        self.mock_smbus_class.assert_called_once_with(0)

    def test_byte_swapping(self):
        """Test byte swapping for little-endian format."""
        ina = INA()

        # Test some known byte swap values
        assert ina._swap_bytes(0x1234) == 0x3412
        assert ina._swap_bytes(0xABCD) == 0xCDAB
        assert ina._swap_bytes(0x0000) == 0x0000
        assert ina._swap_bytes(0xFF00) == 0x00FF

    def test_set_calibration_default(self):
        """Test calibration with default shunt and current."""
        ina = INA()

        # Reset mock to check calibration call
        self.mock_bus.write_word_data.reset_mock()

        ina.set_calibration()

        # Should calculate and write calibration register
        self.mock_bus.write_word_data.assert_called_once()
        call_args = self.mock_bus.write_word_data.call_args[0]
        assert call_args[0] == ina.address
        assert call_args[1] == INARegister.CALIBRATION

        # Check LSB calculations
        assert ina.current_LSB > 0
        assert ina.power_LSB > 0
        assert ina.power_LSB == 25 * ina.current_LSB

    def test_set_calibration_custom_values(self):
        """Test calibration with custom shunt and current values."""
        ina = INA()

        ina.set_calibration(r_shunt_ohms=0.02, max_expected_current_A=5.0)

        # Verify LSB is scaled to max current
        expected_lsb = (5.0 / 32767) * 1e6
        assert abs(ina.current_LSB - expected_lsb) < 0.01

    def test_get_bus_voltage(self):
        """Test reading bus voltage."""
        ina = INA()

        # Mock register returning 9600 (0x2580) which after swap and scaling = 12000mV
        self.mock_bus.read_word_data.return_value = 0x8025  # Will swap to 0x2580

        voltage = ina.get_bus_voltage()

        # 0x2580 = 9600, * 1.25 = 12000mV
        assert voltage == 12000
        self.mock_bus.read_word_data.assert_called_with(ina.address, INARegister.BUS_VOLTAGE)

    def test_get_shunt_voltage(self):
        """Test reading shunt voltage."""
        ina = INA()

        # Mock register returning value that swaps to 1000, * 2.5 = 2500uV
        self.mock_bus.read_word_data.return_value = 0xE803  # Swaps to 0x03E8 (1000)

        voltage = ina.get_shunt_voltage()

        assert voltage == 2500  # 1000 * 2.5
        self.mock_bus.read_word_data.assert_called_with(ina.address, INARegister.SHUNT_VOLTAGE)

    def test_get_current(self):
        """Test reading current."""
        ina = INA()
        ina.current_LSB = 100.0  # 100 µA per bit

        # Mock register returning value that swaps to 500
        self.mock_bus.read_word_data.return_value = 0xF401  # Swaps to 0x01F4 (500)

        current = ina.get_current()

        assert current == 50000  # 500 * 100 µA
        self.mock_bus.read_word_data.assert_called_with(ina.address, INARegister.CURRENT)

    def test_get_power(self):
        """Test reading power."""
        ina = INA()
        ina.power_LSB = 2500.0  # 2500 µW per bit

        # Mock register returning value that swaps to 200
        self.mock_bus.read_word_data.return_value = 0xC800  # Swaps to 0x00C8 (200)

        power = ina.get_power()

        assert power == 500000  # 200 * 2500 µW
        self.mock_bus.read_word_data.assert_called_with(ina.address, INARegister.POWER)

    def test_multiple_reads_use_correct_registers(self):
        """Test that different reads access different registers."""
        ina = INA()
        self.mock_bus.read_word_data.return_value = 0x0000

        ina.get_bus_voltage()
        ina.get_shunt_voltage()
        ina.get_current()
        ina.get_power()

        # Should have called read_word_data 4 times (plus 1 from init calibration read)
        calls = self.mock_bus.read_word_data.call_args_list
        registers_read = [call[0][1] for call in calls]

        assert INARegister.BUS_VOLTAGE in registers_read
        assert INARegister.SHUNT_VOLTAGE in registers_read
        assert INARegister.CURRENT in registers_read
        assert INARegister.POWER in registers_read


if __name__ == '__main__':
    unittest.main()
