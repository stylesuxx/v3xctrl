import unittest
from unittest.mock import MagicMock, patch

from v3xctrl_helper.sei import parse_sei_nal


@patch("v3xctrl_gst.SEIInjector._libgst")
@patch("v3xctrl_gst.SEIInjector.Gst")
class TestSEIInjectorPreEncode(unittest.TestCase):
    def _create_injector(self, mock_gst, mock_libgst):
        mock_gst.PadProbeReturn.OK = 0
        mock_gst.MapFlags.READ = 1

        from v3xctrl_gst.SEIInjector import SEIInjector

        injector = SEIInjector()
        return injector, mock_gst

    def test_captures_timing_by_pts(self, mock_gst, mock_libgst):
        injector, mock_gst = self._create_injector(mock_gst, mock_libgst)

        buffer = MagicMock()
        buffer.pts = 12345
        info = MagicMock()
        info.get_buffer.return_value = buffer

        with patch("v3xctrl_gst.SEIInjector.time") as mock_time:
            mock_time.time.return_value = 1.0
            result = injector.on_pre_encode(MagicMock(), info)

        self.assertEqual(result, mock_gst.PadProbeReturn.OK)
        self.assertIn(12345, injector._pending)
        self.assertEqual(injector._pending[12345], 1_000_000)

    def test_overwrites_same_pts(self, mock_gst, mock_libgst):
        injector, mock_gst = self._create_injector(mock_gst, mock_libgst)

        buffer = MagicMock()
        buffer.pts = 100
        info = MagicMock()
        info.get_buffer.return_value = buffer

        with patch("v3xctrl_gst.SEIInjector.time") as mock_time:
            mock_time.time.return_value = 0.001
            injector.on_pre_encode(MagicMock(), info)

            mock_time.time.return_value = 0.002
            injector.on_pre_encode(MagicMock(), info)

        self.assertEqual(injector._pending[100], 2000)

    def test_multiple_pts_tracked(self, mock_gst, mock_libgst):
        injector, mock_gst = self._create_injector(mock_gst, mock_libgst)

        with patch("v3xctrl_gst.SEIInjector.time") as mock_time:
            for pts_val in [100, 200, 300]:
                buffer = MagicMock()
                buffer.pts = pts_val
                info = MagicMock()
                info.get_buffer.return_value = buffer
                mock_time.time.return_value = pts_val / 1_000_000
                injector.on_pre_encode(MagicMock(), info)

        self.assertEqual(len(injector._pending), 3)
        self.assertEqual(injector._pending[200], 200)


@patch("v3xctrl_gst.SEIInjector._gst_mini_object_unref")
@patch("v3xctrl_gst.SEIInjector._gst_mini_object_ref")
@patch("v3xctrl_gst.SEIInjector._c_ptr", return_value=0x1000)
@patch("v3xctrl_gst.SEIInjector.ctypes")
@patch("v3xctrl_gst.SEIInjector._libgst")
@patch("v3xctrl_gst.SEIInjector.Gst")
class TestSEIInjectorPostEncode(unittest.TestCase):
    def _create_injector(self, mock_gst, mock_libgst):
        mock_gst.PadProbeReturn.OK = 0
        mock_gst.MapFlags.READ = 1

        from v3xctrl_gst.SEIInjector import SEIInjector

        injector = SEIInjector()
        return injector, mock_gst, mock_libgst

    def _make_buffer_with_data(self, pts, data, mock_gst):
        buffer = MagicMock()
        buffer.pts = pts
        buffer.dts = pts + 1
        buffer.duration = 33333
        buffer.offset = 0
        map_info = MagicMock()
        map_info.data = data
        buffer.map.return_value = (True, map_info)
        return buffer

    def test_skips_when_no_pending_timing(self, mock_gst, mock_libgst, mock_ctypes, mock_c_ptr, mock_ref, mock_unref):
        injector, mock_gst, mock_libgst = self._create_injector(mock_gst, mock_libgst)

        buffer = MagicMock()
        buffer.pts = 999
        info = MagicMock()
        info.get_buffer.return_value = buffer

        result = injector.on_post_encode(MagicMock(), info)

        self.assertEqual(result, mock_gst.PadProbeReturn.OK)
        buffer.map.assert_not_called()

    def test_creates_combined_buffer_with_sei_prepended(
        self, mock_gst, mock_libgst, mock_ctypes, mock_c_ptr, mock_ref, mock_unref
    ):
        injector, mock_gst, mock_libgst = self._create_injector(mock_gst, mock_libgst)

        injector._pending[5000] = 123456789

        original_data = b"\x00\x00\x00\x01\x65" + b"\xab" * 20
        buffer = self._make_buffer_with_data(5000, original_data, mock_gst)
        info = MagicMock()
        info.get_buffer.return_value = buffer

        captured_data = []
        mock_gst.Buffer.new_wrapped.side_effect = lambda data: (captured_data.append(bytes(data)), MagicMock())[1]

        injector.on_post_encode(MagicMock(), info)

        self.assertEqual(len(captured_data), 1)
        combined = captured_data[0]

        sei_result = parse_sei_nal(combined)
        self.assertIsNotNone(sei_result)
        self.assertEqual(sei_result, 123456789)

        self.assertTrue(combined.endswith(original_data))

    def test_consumes_pending_entry(self, mock_gst, mock_libgst, mock_ctypes, mock_c_ptr, mock_ref, mock_unref):
        injector, mock_gst, mock_libgst = self._create_injector(mock_gst, mock_libgst)
        injector._pending[5000] = 100

        buffer = self._make_buffer_with_data(5000, b"\x00" * 10, mock_gst)
        info = MagicMock()
        info.get_buffer.return_value = buffer
        mock_gst.Buffer.new_wrapped.return_value = MagicMock()

        injector.on_post_encode(MagicMock(), info)

        self.assertNotIn(5000, injector._pending)

    def test_copies_buffer_metadata(self, mock_gst, mock_libgst, mock_ctypes, mock_c_ptr, mock_ref, mock_unref):
        injector, mock_gst, mock_libgst = self._create_injector(mock_gst, mock_libgst)
        injector._pending[5000] = 100

        buffer = self._make_buffer_with_data(5000, b"\x00" * 10, mock_gst)
        info = MagicMock()
        info.get_buffer.return_value = buffer

        new_buf = MagicMock()
        mock_gst.Buffer.new_wrapped.return_value = new_buf

        injector.on_post_encode(MagicMock(), info)

        self.assertEqual(new_buf.pts, buffer.pts)
        self.assertEqual(new_buf.dts, buffer.dts)
        self.assertEqual(new_buf.duration, buffer.duration)
        self.assertEqual(new_buf.offset, buffer.offset)

    def test_handles_map_failure(self, mock_gst, mock_libgst, mock_ctypes, mock_c_ptr, mock_ref, mock_unref):
        injector, mock_gst, mock_libgst = self._create_injector(mock_gst, mock_libgst)
        injector._pending[5000] = 100

        buffer = MagicMock()
        buffer.pts = 5000
        buffer.map.return_value = (False, None)
        info = MagicMock()
        info.get_buffer.return_value = buffer

        result = injector.on_post_encode(MagicMock(), info)

        self.assertEqual(result, mock_gst.PadProbeReturn.OK)

    def test_unmaps_buffer_after_read(self, mock_gst, mock_libgst, mock_ctypes, mock_c_ptr, mock_ref, mock_unref):
        injector, mock_gst, mock_libgst = self._create_injector(mock_gst, mock_libgst)
        injector._pending[5000] = 100

        buffer = self._make_buffer_with_data(5000, b"\x00" * 10, mock_gst)
        map_info = buffer.map.return_value[1]
        info = MagicMock()
        info.get_buffer.return_value = buffer
        mock_gst.Buffer.new_wrapped.return_value = MagicMock()

        injector.on_post_encode(MagicMock(), info)

        buffer.unmap.assert_called_once_with(map_info)

    def test_refs_new_buffer_and_unrefs_old(self, mock_gst, mock_libgst, mock_ctypes, mock_c_ptr, mock_ref, mock_unref):
        injector, mock_gst, mock_libgst = self._create_injector(mock_gst, mock_libgst)
        injector._pending[5000] = 100

        buffer = self._make_buffer_with_data(5000, b"\x00" * 10, mock_gst)
        info = MagicMock()
        info.get_buffer.return_value = buffer
        mock_gst.Buffer.new_wrapped.return_value = MagicMock()

        injector.on_post_encode(MagicMock(), info)

        mock_ref.assert_called_once()
        mock_unref.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
