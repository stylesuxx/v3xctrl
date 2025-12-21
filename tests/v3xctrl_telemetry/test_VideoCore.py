"""Tests for VideoCore telemetry."""
import unittest
from unittest.mock import patch

from v3xctrl_telemetry.VideoCoreTelemetry import VideoCoreTelemetry, Flags


class TestVideoCoreTelemetry(unittest.TestCase):
    """Test VideoCore throttling detection with mocked vcgencmd."""

    def setUp(self):
        """Set up test fixtures with mocked subprocess."""
        self.subprocess_patcher = patch('v3xctrl_telemetry.VideoCoreTelemetry.subprocess')
        self.mock_subprocess = self.subprocess_patcher.start()

    def tearDown(self):
        """Clean up patches."""
        self.subprocess_patcher.stop()

    def test_initialization(self):
        """Test VideoCoreTelemetry initializes with Flags dataclasses."""
        telemetry = VideoCoreTelemetry()

        assert isinstance(telemetry.current, Flags)
        assert isinstance(telemetry.history, Flags)
        assert telemetry.current.undervolt is False
        assert telemetry.current.freq_capped is False
        assert telemetry.current.throttled is False
        assert telemetry.current.soft_temp_limit is False

    def test_update_no_throttling(self):
        """Test update() with no throttling (0x0)."""
        self.mock_subprocess.check_output.return_value = "throttled=0x0\n"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        # All flags should be False
        assert telemetry.current.undervolt is False
        assert telemetry.current.freq_capped is False
        assert telemetry.current.throttled is False
        assert telemetry.current.soft_temp_limit is False
        assert telemetry.history.undervolt is False
        assert telemetry.history.freq_capped is False
        assert telemetry.history.throttled is False
        assert telemetry.history.soft_temp_limit is False

    def test_update_current_undervolt(self):
        """Test update() with current undervolt (bit 0)."""
        self.mock_subprocess.check_output.return_value = "throttled=0x1"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.current.undervolt is True
        assert telemetry.current.freq_capped is False
        assert telemetry.current.throttled is False
        assert telemetry.current.soft_temp_limit is False

    def test_update_current_freq_capped(self):
        """Test update() with current freq cap (bit 1)."""
        self.mock_subprocess.check_output.return_value = "throttled=0x2"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.current.undervolt is False
        assert telemetry.current.freq_capped is True
        assert telemetry.current.throttled is False
        assert telemetry.current.soft_temp_limit is False

    def test_update_current_throttled(self):
        """Test update() with current throttling (bit 2)."""
        self.mock_subprocess.check_output.return_value = "throttled=0x4"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.current.undervolt is False
        assert telemetry.current.freq_capped is False
        assert telemetry.current.throttled is True
        assert telemetry.current.soft_temp_limit is False

    def test_update_current_soft_temp_limit(self):
        """Test update() with current soft temp limit (bit 3)."""
        self.mock_subprocess.check_output.return_value = "throttled=0x8"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.current.undervolt is False
        assert telemetry.current.freq_capped is False
        assert telemetry.current.throttled is False
        assert telemetry.current.soft_temp_limit is True

    def test_update_history_undervolt(self):
        """Test update() with historical undervolt (bit 16)."""
        self.mock_subprocess.check_output.return_value = "throttled=0x10000"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.current.undervolt is False
        assert telemetry.history.undervolt is True
        assert telemetry.history.freq_capped is False
        assert telemetry.history.throttled is False
        assert telemetry.history.soft_temp_limit is False

    def test_update_history_freq_capped(self):
        """Test update() with historical freq cap (bit 17)."""
        self.mock_subprocess.check_output.return_value = "throttled=0x20000"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.history.undervolt is False
        assert telemetry.history.freq_capped is True
        assert telemetry.history.throttled is False
        assert telemetry.history.soft_temp_limit is False

    def test_update_history_throttled(self):
        """Test update() with historical throttling (bit 18)."""
        self.mock_subprocess.check_output.return_value = "throttled=0x40000"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.history.undervolt is False
        assert telemetry.history.freq_capped is False
        assert telemetry.history.throttled is True
        assert telemetry.history.soft_temp_limit is False

    def test_update_history_soft_temp_limit(self):
        """Test update() with historical soft temp limit (bit 19)."""
        self.mock_subprocess.check_output.return_value = "throttled=0x80000"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.history.undervolt is False
        assert telemetry.history.freq_capped is False
        assert telemetry.history.throttled is False
        assert telemetry.history.soft_temp_limit is True

    def test_update_combined_current_flags(self):
        """Test update() with multiple current flags set."""
        # 0x5 = bits 0 and 2 (undervolt + throttled)
        self.mock_subprocess.check_output.return_value = "throttled=0x5"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.current.undervolt is True
        assert telemetry.current.freq_capped is False
        assert telemetry.current.throttled is True
        assert telemetry.current.soft_temp_limit is False

    def test_update_combined_history_flags(self):
        """Test update() with multiple historical flags set."""
        # 0x50000 = bits 16 and 18
        self.mock_subprocess.check_output.return_value = "throttled=0x50000"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.history.undervolt is True
        assert telemetry.history.freq_capped is False
        assert telemetry.history.throttled is True
        assert telemetry.history.soft_temp_limit is False

    def test_update_current_and_history(self):
        """Test update() with both current and historical flags."""
        # 0x50005 = current undervolt/throttled + historical undervolt/throttled
        self.mock_subprocess.check_output.return_value = "throttled=0x50005"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.current.undervolt is True
        assert telemetry.current.throttled is True
        assert telemetry.history.undervolt is True
        assert telemetry.history.throttled is True

    def test_update_invalid_output_raises_error(self):
        """Test update() raises RuntimeError on invalid vcgencmd output."""
        self.mock_subprocess.check_output.return_value = "invalid output"

        telemetry = VideoCoreTelemetry()

        with self.assertRaises(RuntimeError) as context:
            telemetry.update()

        assert "Unexpected vcgencmd output" in str(context.exception)

    def test_get_byte_no_flags(self):
        """Test get_byte() returns 0x00 when no flags set."""
        self.mock_subprocess.check_output.return_value = "throttled=0x0"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        assert telemetry.get_byte() == 0x00

    def test_get_byte_current_flags(self):
        """Test get_byte() packs current flags into lower nibble."""
        self.mock_subprocess.check_output.return_value = "throttled=0xF"  # All current bits

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        byte = telemetry.get_byte()
        assert byte == 0x0F  # Lower nibble all set

    def test_get_byte_history_flags(self):
        """Test get_byte() packs history flags into upper nibble."""
        self.mock_subprocess.check_output.return_value = "throttled=0xF0000"  # All history bits

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        byte = telemetry.get_byte()
        assert byte == 0xF0  # Upper nibble all set

    def test_get_byte_combined_flags(self):
        """Test get_byte() packs both current and history flags."""
        # Current: 0x5 (bits 0,2) -> lower nibble 0x5
        # History: 0x50000 (bits 16,18) -> upper nibble 0x5
        self.mock_subprocess.check_output.return_value = "throttled=0x50005"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        byte = telemetry.get_byte()
        assert byte == 0x55  # 0101 0101

    def test_get_current(self):
        """Test get_current() returns current Flags object."""
        self.mock_subprocess.check_output.return_value = "throttled=0x1"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        current = telemetry.get_current()
        assert current is telemetry.current
        assert isinstance(current, Flags)
        assert current.undervolt is True

    def test_get_history(self):
        """Test get_history() returns history Flags object."""
        self.mock_subprocess.check_output.return_value = "throttled=0x10000"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        history = telemetry.get_history()
        assert history is telemetry.history
        assert isinstance(history, Flags)
        assert history.undervolt is True

    def test_state_returns_dict(self):
        """Test state() returns dict with current and history."""
        self.mock_subprocess.check_output.return_value = "throttled=0x50005"

        telemetry = VideoCoreTelemetry()
        telemetry.update()

        state = telemetry.state()

        assert isinstance(state, dict)
        assert 'current' in state
        assert 'history' in state
        assert state['current'] is telemetry.current
        assert state['history'] is telemetry.history

    def test_run_vcgencmd_calls_subprocess(self):
        """Test _run_vcgencmd() calls subprocess correctly."""
        self.mock_subprocess.check_output.return_value = "result\n"

        telemetry = VideoCoreTelemetry()
        result = telemetry._run_vcgencmd("get_throttled")

        assert result == "result"
        self.mock_subprocess.check_output.assert_called_once_with(
            ["vcgencmd", "get_throttled"],
            text=True,
            stderr=self.mock_subprocess.STDOUT,
            timeout=1.0,
        )


if __name__ == '__main__':
    unittest.main()
