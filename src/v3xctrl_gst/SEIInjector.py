import ctypes
from typing import Dict, Tuple

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

from v3xctrl_helper import NTPClock, build_sei_nal

# ctypes setup to work around Python GI binding ref leak in Gst.Pad.chain().
# Instead of chain(), we replace the buffer pointer directly in GstPadProbeInfo.data
# (the ctypes equivalent of C macro GST_PAD_PROBE_INFO_DATA(info) = new_buf).
_libgst = ctypes.CDLL('libgstreamer-1.0.so.0')
_gst_mini_object_ref = _libgst.gst_mini_object_ref
_gst_mini_object_ref.restype = ctypes.c_void_p
_gst_mini_object_ref.argtypes = [ctypes.c_void_p]
_gst_mini_object_unref = _libgst.gst_mini_object_unref
_gst_mini_object_unref.restype = None
_gst_mini_object_unref.argtypes = [ctypes.c_void_p]

# Offset of the C pointer inside PyGI wrapper objects (PyGBoxed, PyGObject,
# PyGPointer). All store their C pointer right after PyObject_HEAD which is
# two pointer-sized fields (ob_refcnt + ob_type).
_PYGI_PTR_OFFSET = 2 * ctypes.sizeof(ctypes.c_void_p)


def _c_ptr(pygi_obj):
    """Extract the C pointer from a PyGI-wrapped object."""
    return ctypes.c_void_p.from_address(id(pygi_obj) + _PYGI_PTR_OFFSET).value


# GstPadProbeInfo struct layout — we only need the offset of the `data` field.
class _GstPadProbeInfo(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint),    # GstPadProbeType
        ('id', ctypes.c_ulong),     # gulong
        ('data', ctypes.c_void_p),  # gpointer (GstBuffer* for buffer probes)
    ]


_DATA_OFFSET = _GstPadProbeInfo.data.offset


class SEIInjector:
    def __init__(self, ntp_clock: NTPClock) -> None:
        self._clock = ntp_clock
        self._pending: Dict[int, Tuple[int, int]] = {}

    def on_pre_encode(self, pad, info):
        """Capture wall time + NTP offset when frame enters the encoder."""
        buf = info.get_buffer()
        self._pending[buf.pts] = self._clock.get_time()

        return Gst.PadProbeReturn.OK

    def on_post_encode(self, pad, info):
        """Inject SEI NAL with captured timestamp into encoded frame."""
        buffer = info.get_buffer()
        timing = self._pending.pop(buffer.pts, None)
        if timing is None:
            return Gst.PadProbeReturn.OK

        timestamp_us, offset_us = timing
        sei_bytes = build_sei_nal(timestamp_us, offset_us)

        ok, map_info = buffer.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.PadProbeReturn.OK

        combined = sei_bytes + bytes(map_info.data)
        buffer.unmap(map_info)

        new_buf = Gst.Buffer.new_wrapped(combined)
        new_buf.pts = buffer.pts
        new_buf.dts = buffer.dts
        new_buf.duration = buffer.duration
        new_buf.offset = buffer.offset

        # Replace the buffer in GstPadProbeInfo.data directly, avoiding
        # Gst.Pad.chain() which leaks a ref per call in Python GI bindings.
        # This is the ctypes equivalent of GST_PAD_PROBE_INFO_DATA(info) = new_buf.
        info_ptr = _c_ptr(info)
        new_buf_ptr = _c_ptr(new_buf)

        # Swap: ref new buffer for the pipeline, unref old one we're replacing
        old_buf_ptr = ctypes.c_void_p.from_address(info_ptr + _DATA_OFFSET).value
        _gst_mini_object_ref(new_buf_ptr)
        ctypes.c_void_p.from_address(info_ptr + _DATA_OFFSET).value = new_buf_ptr
        _gst_mini_object_unref(old_buf_ptr)

        return Gst.PadProbeReturn.OK
