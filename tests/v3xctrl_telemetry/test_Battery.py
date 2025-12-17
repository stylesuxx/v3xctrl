"""Tests for Battery monitoring."""
import unittest
from unittest.mock import Mock, patch, MagicMock

from v3xctrl_telemetry.Battery import BatteryTelemetry

# Alias for brevity in tests
Battery = BatteryTelemetry


class TestBattery(unittest.TestCase):
    """Test BatteryTelemetry class with mocked INA sensor."""

    def setUp(self):
        """Set up test fixtures with mocked hardware."""
        self.mock_smbus_patcher = patch('v3xctrl_telemetry.INA.SMBus')
        self.mock_smbus_class = self.mock_smbus_patcher.start()
        self.mock_bus = MagicMock()
        self.mock_smbus_class.return_value = self.mock_bus

    def tearDown(self):
        """Clean up patches."""
        self.mock_smbus_patcher.stop()

    def _mock_voltage(self, millivolts):
        """Helper to mock sensor returning specific voltage."""
        # INA returns voltage in mV, we need to reverse the calculation
        # voltage = raw * 1.25, so raw = voltage / 1.25
        raw_value = int(millivolts / 1.25)
        # Swap bytes for little-endian
        swapped = ((raw_value & 0xFF) << 8) | ((raw_value >> 8) & 0xFF)
        self.mock_bus.read_word_data.return_value = swapped

    def test_initialization_default_values(self):
        """Test Battery initializes with default cell voltages."""
        self._mock_voltage(12000)  # 12V for cell count detection

        battery = Battery()

        assert battery.min_cell_voltage == 3500
        assert battery.max_cell_voltage == 4200
        assert battery.warn_cell_voltage == 3700
        assert battery.voltage == 0
        assert battery.percentage == 100
        assert battery.warning is False

    def test_initialization_custom_values(self):
        """Test Battery initializes with custom voltage thresholds."""
        self._mock_voltage(12000)

        battery = Battery(
            min_cell_voltage=3000,
            max_cell_voltage=4100,
            warn_cell_voltage=3200
        )

        assert battery.min_cell_voltage == 3000
        assert battery.max_cell_voltage == 4100
        assert battery.warn_cell_voltage == 3200

    def test_cell_count_detection_1s(self):
        """Test cell count detection for 1S battery (~4V)."""
        self._mock_voltage(3850)  # 3.85V, typical 1S voltage

        battery = Battery()

        assert battery.cell_count == 1

    def test_cell_count_detection_2s(self):
        """Test cell count detection for 2S battery (~8V)."""
        self._mock_voltage(7800)  # 7.8V, typical 2S voltage

        battery = Battery()

        assert battery.cell_count == 2

    def test_cell_count_detection_3s(self):
        """Test cell count detection for 3S battery (~12V)."""
        self._mock_voltage(11700)  # 11.7V, typical 3S voltage

        battery = Battery()

        assert battery.cell_count == 3

    def test_cell_count_detection_4s(self):
        """Test cell count detection for 4S battery (~16V)."""
        self._mock_voltage(15600)  # 15.6V, typical 4S voltage

        battery = Battery()

        assert battery.cell_count == 4

    def test_cell_count_minimum_is_one(self):
        """Test cell count never goes below 1 (prevents division by zero)."""
        self._mock_voltage(1)  # Very low voltage

        battery = Battery()

        assert battery.cell_count >= 1

    def test_update_reads_voltage(self):
        """Test update() reads current voltage from sensor."""
        self._mock_voltage(12000)
        battery = Battery()

        self._mock_voltage(11400)  # Change voltage
        battery.update()

        assert battery.voltage == 11400

    def test_update_calculates_average_voltage(self):
        """Test update() calculates average cell voltage."""
        self._mock_voltage(12000)
        battery = Battery()
        assert battery.cell_count == 3

        self._mock_voltage(11700)
        battery.update()

        # 11700 / 3 = 3900
        assert battery.average_voltage == 3900

    def test_percentage_calculation_full_battery(self):
        """Test percentage calculation for fully charged battery."""
        self._mock_voltage(12000)
        battery = Battery(min_cell_voltage=3500, max_cell_voltage=4200)
        assert battery.cell_count == 3

        # 3S fully charged: 3 * 4200 = 12600mV
        self._mock_voltage(12600)
        battery.update()

        assert battery.percentage == 100

    def test_percentage_calculation_empty_battery(self):
        """Test percentage calculation for empty battery."""
        self._mock_voltage(12000)
        battery = Battery(min_cell_voltage=3500, max_cell_voltage=4200)
        assert battery.cell_count == 3

        # 3S empty: 3 * 3500 = 10500mV
        self._mock_voltage(10500)
        battery.update()

        assert battery.percentage == 0

    def test_percentage_calculation_mid_battery(self):
        """Test percentage calculation for half-charged battery."""
        self._mock_voltage(12000)
        battery = Battery(min_cell_voltage=3500, max_cell_voltage=4200)
        assert battery.cell_count == 3

        # 3S half: 3 * 3850 = 11550mV (halfway between 3500-4200)
        self._mock_voltage(11550)
        battery.update()

        # (11550 - 10500) / (12600 - 10500) * 100 = 50%
        assert 49 <= battery.percentage <= 51

    def test_percentage_clamped_at_100(self):
        """Test percentage doesn't exceed 100% for overcharged batteries."""
        self._mock_voltage(12000)
        battery = Battery(min_cell_voltage=3500, max_cell_voltage=4200)

        # Overcharged voltage
        self._mock_voltage(15000)
        battery.update()

        assert battery.percentage == 100

    def test_percentage_clamped_at_0(self):
        """Test percentage doesn't go below 0% for overdischarged batteries."""
        self._mock_voltage(12000)
        battery = Battery(min_cell_voltage=3500, max_cell_voltage=4200)

        # Overdischarged voltage
        self._mock_voltage(8000)
        battery.update()

        assert battery.percentage == 0

    def test_warning_triggered_below_threshold(self):
        """Test warning is set when cell voltage drops below threshold."""
        self._mock_voltage(12000)
        battery = Battery(
            min_cell_voltage=3500,
            max_cell_voltage=4200,
            warn_cell_voltage=3700
        )
        assert battery.cell_count == 3

        # 3S with cells at 3650mV (below 3700 warning)
        self._mock_voltage(10950)  # 3 * 3650
        battery.update()

        assert battery.warning is True

    def test_warning_not_triggered_above_threshold(self):
        """Test warning is not set when cell voltage is above threshold."""
        self._mock_voltage(12000)
        battery = Battery(
            min_cell_voltage=3500,
            max_cell_voltage=4200,
            warn_cell_voltage=3700
        )
        assert battery.cell_count == 3

        # 3S with cells at 3900mV (above 3700 warning)
        self._mock_voltage(11700)  # 3 * 3900
        battery.update()

        assert battery.warning is False

    def test_warning_at_exact_threshold(self):
        """Test warning behavior at exact threshold voltage."""
        self._mock_voltage(12000)
        battery = Battery(warn_cell_voltage=3700)
        assert battery.cell_count == 3

        # Exactly at threshold: 3 * 3700 = 11100mV
        self._mock_voltage(11100)
        battery.update()

        # Should trigger warning (<=)
        assert battery.warning is True

    def test_get_volts_conversion(self):
        """Test get_volts() converts millivolts to volts."""
        self._mock_voltage(12000)
        battery = Battery()

        self._mock_voltage(11700)
        battery.update()

        volts = battery.get_volts()
        assert volts == 11.7

    def test_multiple_updates(self):
        """Test multiple update cycles work correctly."""
        self._mock_voltage(12000)
        battery = Battery()

        # First update
        self._mock_voltage(12600)
        battery.update()
        assert battery.percentage == 100
        assert battery.warning is False

        # Second update - voltage drops
        self._mock_voltage(11550)
        battery.update()
        assert 49 <= battery.percentage <= 51
        assert battery.warning is False

        # Third update - voltage drops to warning level
        self._mock_voltage(10950)
        battery.update()
        assert battery.percentage < 30
        assert battery.warning is True


if __name__ == '__main__':
    unittest.main()
