import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_gst.Streamer import Streamer


@patch("v3xctrl_gst.Streamer.ControlServer")
@patch("v3xctrl_gst.Streamer.Gst")
class TestNetworkUnreachableSuppression(unittest.TestCase):
    def _create_streamer(self, mock_gst: MagicMock, mock_cs: MagicMock) -> Streamer:
        return Streamer(host="127.0.0.1", port=5000, bind_port=5001)

    def _make_udpsink_warning(self, mock_gst: MagicMock) -> MagicMock:
        message = MagicMock()
        message.type = mock_gst.MessageType.WARNING
        message.src.get_name.return_value = "udpsink"
        error = MagicMock()
        message.parse_warning.return_value = (error, "sendto: Network is unreachable (101)")
        return message

    def _make_other_warning(self, mock_gst: MagicMock, text: str) -> MagicMock:
        message = MagicMock()
        message.type = mock_gst.MessageType.WARNING
        message.src.get_name.return_value = "encoder"
        error = MagicMock()
        error.__str__ = lambda self: text
        message.parse_warning.return_value = (error, "debug info")
        return message

    def test_first_unreachable_warning_is_logged(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)
        message = self._make_udpsink_warning(mock_gst)

        with patch("v3xctrl_gst.Streamer.logger") as mock_logger, patch("v3xctrl_gst.Streamer.GLib"):
            streamer._on_message(MagicMock(), message)

        mock_logger.warning.assert_called_once_with("Network is unreachable")
        self.assertTrue(streamer._udpsink_network_down)

    def test_subsequent_warnings_are_suppressed(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)
        message = self._make_udpsink_warning(mock_gst)

        with patch("v3xctrl_gst.Streamer.logger") as mock_logger, patch("v3xctrl_gst.Streamer.GLib"):
            streamer._on_message(MagicMock(), message)
            streamer._on_message(MagicMock(), message)
            streamer._on_message(MagicMock(), message)

        mock_logger.warning.assert_called_once_with("Network is unreachable")

    def test_non_network_warnings_are_not_affected(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)
        message = self._make_other_warning(mock_gst, "Some other warning")

        with patch("v3xctrl_gst.Streamer.logger") as mock_logger:
            streamer._on_message(MagicMock(), message)

        mock_logger.warning.assert_called_once_with("Warning: Some other warning, debug info")
        self.assertFalse(streamer._udpsink_network_down)

    def test_recovery_timeout_scheduled_on_warning(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)
        message = self._make_udpsink_warning(mock_gst)

        with patch("v3xctrl_gst.Streamer.GLib") as mock_glib:
            mock_glib.timeout_add.return_value = 42
            streamer._on_message(MagicMock(), message)

        mock_glib.timeout_add.assert_called_once_with(1000, streamer._on_recovery_timeout)
        self.assertEqual(streamer._udpsink_recovery_timeout_id, 42)

    def test_recovery_timeout_rescheduled_on_subsequent_warning(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)
        message = self._make_udpsink_warning(mock_gst)

        with patch("v3xctrl_gst.Streamer.GLib") as mock_glib:
            mock_glib.timeout_add.side_effect = [42, 43]
            streamer._on_message(MagicMock(), message)
            streamer._on_message(MagicMock(), message)

        mock_glib.source_remove.assert_called_once_with(42)
        self.assertEqual(streamer._udpsink_recovery_timeout_id, 43)

    def test_recovery_timeout_clears_error_state(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)
        streamer._udpsink_network_down = True
        streamer._udpsink_recovery_timeout_id = 42

        with patch("v3xctrl_gst.Streamer.logger") as mock_logger:
            streamer._on_recovery_timeout()

        self.assertFalse(streamer._udpsink_network_down)
        self.assertIsNone(streamer._udpsink_recovery_timeout_id)
        mock_logger.info.assert_called_once_with("Network recovered")

    def test_new_warning_after_recovery_logs_again(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)
        message = self._make_udpsink_warning(mock_gst)

        with patch("v3xctrl_gst.Streamer.logger") as mock_logger, patch("v3xctrl_gst.Streamer.GLib"):
            # First outage
            streamer._on_message(MagicMock(), message)
            # Recovery
            streamer._on_recovery_timeout()
            # Second outage
            streamer._on_message(MagicMock(), message)

        self.assertEqual(mock_logger.warning.call_count, 2)


@patch("v3xctrl_gst.Streamer.ControlServer")
@patch("v3xctrl_gst.Streamer.Gst")
class TestUdpQueueOverrunSuppression(unittest.TestCase):
    def _create_streamer(self, mock_gst: MagicMock, mock_cs: MagicMock) -> Streamer:
        return Streamer(host="127.0.0.1", port=5000, bind_port=5001)

    def test_first_overrun_is_logged(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)

        with patch("v3xctrl_gst.Streamer.logger") as mock_logger, patch("v3xctrl_gst.Streamer.GLib"):
            streamer._on_udp_queue_overrun(MagicMock())

        mock_logger.error.assert_called_once_with("UDP queue overrun - dropping frames!")
        self.assertTrue(streamer._udp_queue_overrun_active)

    def test_subsequent_overruns_are_suppressed(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)

        with patch("v3xctrl_gst.Streamer.logger") as mock_logger, patch("v3xctrl_gst.Streamer.GLib"):
            streamer._on_udp_queue_overrun(MagicMock())
            streamer._on_udp_queue_overrun(MagicMock())
            streamer._on_udp_queue_overrun(MagicMock())

        mock_logger.error.assert_called_once_with("UDP queue overrun - dropping frames!")

    def test_overflow_time_updated_on_every_overrun(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)

        with patch("v3xctrl_gst.Streamer.GLib"):
            streamer._on_udp_queue_overrun(MagicMock())
            time_after_first = streamer.last_udp_overflow_time

            streamer._on_udp_queue_overrun(MagicMock())
            time_after_second = streamer.last_udp_overflow_time

        self.assertGreater(time_after_first, 0)
        self.assertGreaterEqual(time_after_second, time_after_first)

    def test_recovery_timeout_scheduled_on_overrun(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)

        with patch("v3xctrl_gst.Streamer.GLib") as mock_glib:
            mock_glib.timeout_add.return_value = 42
            streamer._on_udp_queue_overrun(MagicMock())

        mock_glib.timeout_add.assert_called_once_with(1000, streamer._on_udp_queue_overrun_recovery_timeout)
        self.assertEqual(streamer._udp_queue_overrun_recovery_timeout_id, 42)

    def test_recovery_timeout_rescheduled_on_subsequent_overrun(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)

        with patch("v3xctrl_gst.Streamer.GLib") as mock_glib:
            mock_glib.timeout_add.side_effect = [42, 43]
            streamer._on_udp_queue_overrun(MagicMock())
            streamer._on_udp_queue_overrun(MagicMock())

        mock_glib.source_remove.assert_called_once_with(42)
        self.assertEqual(streamer._udp_queue_overrun_recovery_timeout_id, 43)

    def test_recovery_timeout_clears_state(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)
        streamer._udp_queue_overrun_active = True
        streamer._udp_queue_overrun_recovery_timeout_id = 42

        with patch("v3xctrl_gst.Streamer.logger") as mock_logger:
            streamer._on_udp_queue_overrun_recovery_timeout()

        self.assertFalse(streamer._udp_queue_overrun_active)
        self.assertIsNone(streamer._udp_queue_overrun_recovery_timeout_id)
        mock_logger.info.assert_called_once_with("UDP queue recovered")

    def test_new_overrun_after_recovery_logs_again(self, mock_gst: MagicMock, mock_cs: MagicMock):
        streamer = self._create_streamer(mock_gst, mock_cs)

        with patch("v3xctrl_gst.Streamer.logger") as mock_logger, patch("v3xctrl_gst.Streamer.GLib"):
            streamer._on_udp_queue_overrun(MagicMock())
            streamer._on_udp_queue_overrun_recovery_timeout()
            streamer._on_udp_queue_overrun(MagicMock())

        self.assertEqual(mock_logger.error.call_count, 2)


if __name__ == "__main__":
    unittest.main()
