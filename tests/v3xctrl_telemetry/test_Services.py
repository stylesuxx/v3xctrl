"""Tests for Services telemetry."""
import unittest
from unittest.mock import patch

from v3xctrl_telemetry.Services import ServiceTelemetry, Services


class TestServiceTelemetry(unittest.TestCase):
    """Test service status monitoring with mocked subprocess."""

    def setUp(self):
        """Set up test fixtures."""
        self.subprocess_patcher = patch('v3xctrl_telemetry.Services.subprocess')
        self.mock_subprocess = self.subprocess_patcher.start()

    def tearDown(self):
        """Clean up patches."""
        self.subprocess_patcher.stop()

    def test_initialization(self):
        """Test ServiceTelemetry initializes with Services dataclass."""
        telemetry = ServiceTelemetry()

        assert isinstance(telemetry.services, Services)
        assert telemetry.services.v3xctrl_video is False
        assert telemetry.services.v3xctrl_debug is False

    def test_is_active_service_running(self):
        """Test _is_active returns True when service is active."""
        self.mock_subprocess.call.return_value = 0  # systemctl returns 0 for active

        telemetry = ServiceTelemetry()
        result = telemetry._is_active("test.service")

        assert result is True
        self.mock_subprocess.call.assert_called_once()

    def test_is_active_service_not_running(self):
        """Test _is_active returns False when service is inactive."""
        self.mock_subprocess.call.return_value = 3  # systemctl returns non-zero for inactive

        telemetry = ServiceTelemetry()
        result = telemetry._is_active("test.service")

        assert result is False

    def test_update_checks_all_services(self):
        """Test update() checks status of all services in dataclass."""
        # Mock first service active, second inactive
        self.mock_subprocess.call.side_effect = [0, 3]

        telemetry = ServiceTelemetry()
        telemetry.update()

        assert telemetry.services.v3xctrl_video is True
        assert telemetry.services.v3xctrl_debug is False

        # Should have been called twice (once for each service)
        assert self.mock_subprocess.call.call_count == 2

    def test_update_converts_underscores_to_hyphens(self):
        """Test update() correctly converts field names to service names."""
        self.mock_subprocess.call.return_value = 0

        telemetry = ServiceTelemetry()
        telemetry.update()

        # Check that service names were converted correctly
        calls = self.mock_subprocess.call.call_args_list
        called_services = [call[0][0][3] for call in calls]  # Index 3 is the service name

        assert "v3xctrl-video.service" in called_services
        assert "v3xctrl-debug.service" in called_services

    def test_state_returns_services_object(self):
        """Test state() returns the services dataclass."""
        telemetry = ServiceTelemetry()

        state = telemetry.state()

        assert state is telemetry.services
        assert isinstance(state, Services)

    def test_get_byte_no_services(self):
        """Test get_byte() returns 0x00 when no services active."""
        self.mock_subprocess.call.return_value = 3  # All services inactive

        telemetry = ServiceTelemetry()
        telemetry.update()

        assert telemetry.get_byte() == 0x00

    def test_get_byte_video_only(self):
        """Test get_byte() with only v3xctrl_video active (bit 0)."""
        self.mock_subprocess.call.side_effect = [0, 3]  # video active, debug inactive

        telemetry = ServiceTelemetry()
        telemetry.update()

        assert telemetry.get_byte() == 0x01  # 0000 0001

    def test_get_byte_debug_only(self):
        """Test get_byte() with only v3xctrl_debug active (bit 1)."""
        self.mock_subprocess.call.side_effect = [3, 0]  # video inactive, debug active

        telemetry = ServiceTelemetry()
        telemetry.update()

        assert telemetry.get_byte() == 0x02  # 0000 0010

    def test_get_byte_both_services(self):
        """Test get_byte() with both services active."""
        self.mock_subprocess.call.side_effect = [0, 0]  # Both active

        telemetry = ServiceTelemetry()
        telemetry.update()

        assert telemetry.get_byte() == 0x03  # 0000 0011


if __name__ == '__main__':
    unittest.main()
