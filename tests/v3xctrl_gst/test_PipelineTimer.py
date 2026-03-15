import time
from unittest.mock import MagicMock, patch

import pytest

from v3xctrl_gst.PipelineTimer import PipelineTimer

GST_SECOND = 1_000_000_000
GST_MSECOND = 1_000_000


@pytest.fixture
def timer():
    return PipelineTimer(log_interval=1.0)


class TestEnableDisable:
    def test_disabled_by_default(self, timer):
        assert timer.enabled is False

    def test_enable(self, timer):
        timer.enable()
        assert timer.enabled is True

    def test_disable(self, timer):
        timer.enable()
        timer.disable()
        assert timer.enabled is False

    def test_enable_clears_state(self, timer):
        timer.enable()
        timer._data[123] = {"source": 1.0}
        timer._stats["capture"].append(5.0)
        timer._debug["source_probe"] = 10

        timer.enable()
        assert timer._data == {}
        assert timer._stats["capture"] == []
        assert timer._debug["source_probe"] == 0


class TestNoOpWhenDisabled:
    def test_on_source_buffer_noop(self, timer):
        pipeline = MagicMock()
        timer.on_source_buffer(100, pipeline)
        assert timer._data == {}
        pipeline.get_clock.assert_not_called()

    def test_on_capsfilter_buffer_noop(self, timer):
        timer.on_capsfilter_buffer(100)
        assert timer._debug["capsfilter_probe"] == 0

    def test_on_encoder_buffer_noop(self, timer):
        timer.on_encoder_buffer(100)
        assert timer._debug["encoder_probe"] == 0

    def test_on_udp_buffer_noop(self, timer):
        timer.on_udp_buffer(100)
        assert timer._debug["udp_miss"] == 0


class TestSourceBuffer:
    def test_records_source_timing(self, timer):
        timer.enable()

        pipeline = MagicMock()
        clock = MagicMock()
        pipeline.get_clock.return_value = clock
        clock.get_time.return_value = 2 * GST_SECOND
        pipeline.get_base_time.return_value = 0

        pts = 1 * GST_SECOND
        timer.on_source_buffer(pts, pipeline)

        assert pts in timer._data
        assert "source" in timer._data[pts]
        assert "capture_delay" in timer._data[pts]
        assert timer._data[pts]["capture_delay"] == pytest.approx(1000.0)
        assert timer._debug["source_probe"] == 1


class TestCapsfilterBuffer:
    def test_records_capsfilter_timing(self, timer):
        timer.enable()
        pts = 100
        timer._data[pts] = {"source": time.monotonic()}

        timer.on_capsfilter_buffer(pts)

        assert "capsfilter" in timer._data[pts]
        assert timer._debug["capsfilter_probe"] == 1

    def test_capsfilter_miss(self, timer):
        timer.enable()
        timer.on_capsfilter_buffer(999)

        assert timer._debug["capsfilter_miss"] == 1


class TestEncoderBuffer:
    def test_records_encoder_timing(self, timer):
        timer.enable()
        pts = 100
        timer._data[pts] = {"source": 1.0, "capsfilter": 1.001}

        timer.on_encoder_buffer(pts)

        assert "encoder" in timer._data[pts]
        assert timer._debug["encoder_probe"] == 1

    def test_encoder_miss(self, timer):
        timer.enable()
        timer.on_encoder_buffer(999)

        assert timer._debug["encoder_miss"] == 1


class TestUdpBuffer:
    def test_udp_miss_when_no_data(self, timer):
        timer.enable()
        timer.on_udp_buffer(999)

        assert timer._debug["udp_miss"] == 1

    def test_incomplete_when_missing_stages(self, timer):
        timer.enable()
        pts = 100
        timer._data[pts] = {"source": 1.0}

        timer.on_udp_buffer(pts)

        assert timer._debug["incomplete"] == 1

    def test_full_pipeline_timing(self, timer):
        timer.enable()
        pts = 100
        now = time.monotonic()
        timer._data[pts] = {
            "source": now - 0.010,
            "capture_delay": 5.0,
            "capsfilter": now - 0.008,
            "encoder": now - 0.003,
        }

        timer.on_udp_buffer(pts)

        assert pts not in timer._data
        assert len(timer._stats["capture"]) == 1
        assert len(timer._stats["encode"]) == 1
        assert len(timer._stats["package"]) == 1
        assert timer._stats["capture"][0] == pytest.approx(5.0)
        assert timer._debug["udp_probe"] == 1

    def test_old_entries_cleaned_up(self, timer):
        timer.enable()
        for i in range(105):
            timer._data[i] = {"source": 1.0}

        pts = 200
        now = time.monotonic()
        timer._data[pts] = {
            "source": now,
            "capture_delay": 0,
            "capsfilter": now,
            "encoder": now,
        }

        timer.on_udp_buffer(pts)

        assert len(timer._data) <= 105


class TestLogStats:
    def test_log_stats_called_on_interval(self, timer):
        timer = PipelineTimer(log_interval=0.0)
        timer.enable()

        pts = 100
        now = time.monotonic()
        timer._data[pts] = {
            "source": now - 0.010,
            "capture_delay": 5.0,
            "capsfilter": now - 0.008,
            "encoder": now - 0.003,
        }
        timer._last_log = now - 1.0

        with patch("v3xctrl_gst.PipelineTimer.logger") as mock_logger:
            timer.on_udp_buffer(pts)
            mock_logger.debug.assert_called_once()
            assert "[TIMING]" in mock_logger.debug.call_args[0][0]

        assert timer._stats["capture"] == []

    def test_log_stats_skipped_when_empty(self, timer):
        timer.enable()

        with patch("v3xctrl_gst.PipelineTimer.logger") as mock_logger:
            timer._log_stats()
            mock_logger.debug.assert_not_called()
