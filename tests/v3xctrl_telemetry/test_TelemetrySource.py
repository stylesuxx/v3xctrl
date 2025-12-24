"""Tests for TelemetrySource protocol."""
import sys
import unittest
from unittest.mock import patch, MagicMock

# Mock GStreamer before any imports
sys.modules['gi'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()
sys.modules['gi.repository.Gst'] = MagicMock()
sys.modules['gi.repository.GLib'] = MagicMock()

from v3xctrl_telemetry import (
    TelemetrySource,
    BatteryTelemetry,
    BatteryState,
    ServiceTelemetry,
    Services,
    VideoCoreTelemetry,
    Flags,
    GstTelemetry,
    Stats
)


class TestTelemetrySourceProtocol(unittest.TestCase):
    """Test that all telemetry classes implement TelemetrySource protocol."""

    def setUp(self):
        """Set up test fixtures with mocked hardware."""
        self.smbus_patcher = patch('v3xctrl_telemetry.INA.SMBus')
        self.mock_smbus = self.smbus_patcher.start()

        self.subprocess_patcher = patch('v3xctrl_telemetry.ServiceTelemetry.subprocess')
        self.mock_subprocess_service = self.subprocess_patcher.start()

        self.vcgencmd_patcher = patch('v3xctrl_telemetry.VideoCoreTelemetry.subprocess')
        self.mock_subprocess_vc = self.vcgencmd_patcher.start()
        self.mock_subprocess_vc.check_output.return_value = "throttled=0x0"

    def tearDown(self):
        """Clean up patches."""
        self.smbus_patcher.stop()
        self.subprocess_patcher.stop()
        self.vcgencmd_patcher.stop()

    def test_battery_implements_protocol(self):
        """Test BatteryTelemetry implements TelemetrySource protocol."""
        battery = BatteryTelemetry()

        assert isinstance(battery, TelemetrySource)
        assert hasattr(battery, 'update')
        assert callable(battery.update)

    def test_service_implements_protocol(self):
        """Test ServiceTelemetry implements TelemetrySource protocol."""
        service = ServiceTelemetry()

        assert isinstance(service, TelemetrySource)
        assert hasattr(service, 'update')
        assert callable(service.update)

    def test_videocore_implements_protocol(self):
        """Test VideoCoreTelemetry implements TelemetrySource protocol."""
        videocore = VideoCoreTelemetry()

        assert isinstance(videocore, TelemetrySource)
        assert hasattr(videocore, 'update')
        assert callable(videocore.update)

    def test_gst_implements_protocol(self):
        """Test GstTelemetry implements TelemetrySource protocol."""
        gst = GstTelemetry()

        assert isinstance(gst, TelemetrySource)
        assert hasattr(gst, 'update')
        assert callable(gst.update)


class TestGetStateMethods(unittest.TestCase):
    """Test get_state() methods across all telemetry classes."""

    def setUp(self):
        """Set up test fixtures with mocked hardware."""
        self.smbus_patcher = patch('v3xctrl_telemetry.INA.SMBus')
        self.mock_smbus = self.smbus_patcher.start()

        self.subprocess_patcher = patch('v3xctrl_telemetry.ServiceTelemetry.subprocess')
        self.mock_subprocess_service = self.subprocess_patcher.start()

        self.vcgencmd_patcher = patch('v3xctrl_telemetry.VideoCoreTelemetry.subprocess')
        self.mock_subprocess_vc = self.vcgencmd_patcher.start()
        self.mock_subprocess_vc.check_output.return_value = "throttled=0x0"

    def tearDown(self):
        """Clean up patches."""
        self.smbus_patcher.stop()
        self.subprocess_patcher.stop()
        self.vcgencmd_patcher.stop()

    def test_battery_get_state(self):
        """Test BatteryTelemetry.get_state() returns BatteryState."""
        battery = BatteryTelemetry()
        state = battery.get_state()

        assert isinstance(state, BatteryState)
        assert hasattr(state, 'voltage')
        assert hasattr(state, 'average_voltage')
        assert hasattr(state, 'percentage')
        assert hasattr(state, 'warning')
        assert hasattr(state, 'cell_count')

    def test_service_get_state(self):
        """Test ServiceTelemetry.get_state() returns Services."""
        service = ServiceTelemetry()
        state = service.get_state()

        assert isinstance(state, Services)
        assert hasattr(state, 'v3xctrl_video')
        assert hasattr(state, 'v3xctrl_debug')

    def test_videocore_get_state(self):
        """Test VideoCoreTelemetry.get_state() returns dict with Flags."""
        videocore = VideoCoreTelemetry()
        state = videocore.get_state()

        assert isinstance(state, dict)
        assert 'current' in state
        assert 'history' in state
        assert isinstance(state['current'], Flags)
        assert isinstance(state['history'], Flags)

    def test_gst_get_state(self):
        """Test GstTelemetry.get_state() returns Stats."""
        gst = GstTelemetry()
        state = gst.get_state()

        assert isinstance(state, Stats)
        assert hasattr(state, 'recording')

    def test_battery_state_is_dataclass(self):
        """Test BatteryTelemetry.get_state() returns a proper dataclass instance."""
        battery = BatteryTelemetry()
        state = battery.get_state()

        # Verify it's a dataclass with expected attributes
        from dataclasses import is_dataclass
        assert is_dataclass(state)
        assert state.voltage == 0
        assert state.average_voltage == 0
        assert state.percentage == 100
        assert state.warning is False
        assert state.cell_count >= 1


if __name__ == '__main__':
    unittest.main()
