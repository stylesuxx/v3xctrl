from typing import Dict, Tuple

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

from v3xctrl_helper import NTPClock, build_sei_nal


class SEIInjector:
    def __init__(self, ntp_clock: NTPClock) -> None:
        self._clock = ntp_clock
        self._pending: Dict[int, Tuple[int, int]] = {}

    def on_pre_encode(self, pad, info):
        """Capture wall time + NTP offset when frame enters the encoder."""
        buffer = info.get_buffer()
        pts = buffer.pts

        self._pending[pts] = self._clock.get_time()

        return Gst.PadProbeReturn.OK

    def on_post_encode(self, pad, info):
        """Inject SEI NAL with captured timestamp into encoded frame."""
        buffer = info.get_buffer()
        pts = buffer.pts

        timing = self._pending.pop(pts, None)
        if timing is None:
            return Gst.PadProbeReturn.OK

        timestamp_us, offset_us = timing
        sei_bytes = build_sei_nal(timestamp_us, offset_us)

        # Map original buffer, build new buffer with SEI prepended
        ok, map_info = buffer.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.PadProbeReturn.OK

        combined = sei_bytes + bytes(map_info.data)
        buffer.unmap(map_info)

        new_buf = Gst.Buffer.new_allocate(None, len(combined), None)
        new_buf.fill(0, combined)
        new_buf.pts = buffer.pts
        new_buf.dts = buffer.dts
        new_buf.duration = buffer.duration
        new_buf.offset = buffer.offset

        # Push directly to downstream sink pad, bypassing src pad probes
        peer = pad.get_peer()
        peer.chain(new_buf)

        return Gst.PadProbeReturn.HANDLED
