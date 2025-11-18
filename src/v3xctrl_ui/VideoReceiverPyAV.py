import logging
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Callable

import av

from v3xctrl_ui.VideoReceiver import VideoReceiver


class VideoReceiverPyAV(VideoReceiver):
    """
    PyAV-based video receiver implementation.


    PyAV uses ffmpeg under the hood. Parametrization can be a bit tricky at
    times since there is no real feedback if passed options are applied and
    take effect, so changing things is a bit of trial and error.

    NOTE: FFMPEG will display older frames if they arrive after newer frames
          This is behavior that we do not want so we check packets manually and
          drop them if they are older than a given threshold.
    """

    def __init__(
        self,
        port: int,
        keep_alive: Callable[[], None],
        log_interval: int = 10,
        history_size: int = 100,
        max_frame_age_ms: int = 500,
        render_ratio: int = 0,
    ) -> None:
        super().__init__(
            port,
            keep_alive,
            log_interval,
            history_size,
            max_frame_age_ms,
            render_ratio
        )

        self.container = None
        self.sdp_path = Path(tempfile.gettempdir()) / f"rtp_{self.port}.sdp"
        self.container_lock = threading.Lock()
        self.thread_count = str(min(os.cpu_count() or 1, 4))

        self.latest_packet_pts = None

        self.container_options = {
            "fflags": "nobuffer+flush_packets+discardcorrupt+nofillin",
            "protocol_whitelist": "file,udp,rtp",
            "analyzeduration": "1",
            "probesize": "32",
        }

        self.codec_options = {
            "threads": self.thread_count,
            "flags": "low_delay",
            "flags2": "fast"
        }

    def _setup(self) -> None:
        """Setup SDP file."""
        self._write_sdp()

    def _main_loop(self) -> None:
        while self.running.is_set():
            while self.running.is_set():
                try:
                    with self.container_lock:
                        start_time = time.monotonic()
                        self.container = av.open(
                            str(self.sdp_path),
                            format="sdp",
                            options=self.container_options,
                            timeout=2
                        )
                        open_time = time.monotonic() - start_time
                        logging.info(f"Container opened in {open_time:.3f}s")

                        self.latest_packet_pts = None
                    break
                except av.AVError as e:
                    logging.warning(f"av.open() failed: {e}")
                    time.sleep(0.5)

            if self.container:
                stream = self.container.streams.video[0]
                stream.codec_context.thread_type = "AUTO"
                stream.codec_context.options = self.codec_options

                try:
                    while self.running.is_set():
                        if self.container:
                            for packet in self.container.demux(stream):
                                if not self.running.is_set():
                                    break

                                self.packet_count += 1

                                if self._should_drop_packet_by_age(packet, stream):
                                    self.dropped_old_frames += 1
                                    continue

                                decoded_frames = list(packet.decode())
                                if decoded_frames:
                                    for frame in decoded_frames:
                                        rgb_frame = frame.to_ndarray(format="rgb24")
                                        self._update_frame(rgb_frame)
                                else:
                                    self.dropped_empty_frames += 1

                                self._log_stats_if_needed()

                except av.AVError as e:
                    logging.warning(f"Stream decode error: {e}")
                    try:
                        with self.container_lock:
                            if self.container:
                                self.container.close()
                                self.container = None
                    except Exception as e:
                        logging.warning(f"Container close failed during error recovery: {e}")

                    finally:
                        # We are not getting a video stream, send keep alive
                        self.keep_alive()

                except Exception as e:
                    logging.exception(f"Unexpected error in receiver thread: {e}")

                finally:
                    with self.frame_lock:
                        self.frame = None

                    try:
                        with self.container_lock:
                            if self.container:
                                self.container.close()
                                self.container = None
                    except Exception as e:
                        logging.warning(f"Container close failed: {e}")

    def _cleanup(self) -> None:
        """Cleanup container and SDP file."""
        with self.container_lock:
            if self.container:
                try:
                    self.container.close()
                except Exception as e:
                    logging.warning(f"Container close failed during cleanup: {e}")
                finally:
                    self.container = None

        try:
            if self.sdp_path.exists():
                self.sdp_path.unlink()
        except Exception as e:
            logging.warning(f"SDP file cleanup failed: {e}")

    def _write_sdp(self) -> None:
        """Write SDP file for RTP stream."""
        sdp_text = f"""\
v=0
o=- 0 0 IN IP4 127.0.0.1
s=RTP Stream
c=IN IP4 0.0.0.0
t=0 0
m=video {self.port} RTP/AVP 96
a=rtpmap:96 H264/90000
a=rtcp-fb:96 nack
a=rtcp-fb:96 nack pli
a=recvonly
"""
        with open(self.sdp_path, "w", newline="\n") as f:
            f.write(sdp_text)
            f.flush()
            os.fsync(f.fileno())

    def _should_drop_packet_by_age(self, packet: av.Packet, stream: av.VideoStream) -> bool:
        if packet.pts is None:
            return False

        # Track latest packet pts (no conversion needed)
        if self.latest_packet_pts is None:
            self.latest_packet_pts = packet.pts
            return False

        # Update latest pts if this packet is newer
        time_base = stream.time_base
        time_diff = (self.latest_packet_pts - packet.pts) * time_base
        if time_diff >= self.max_age_seconds:
            return True

        if packet.pts > self.latest_packet_pts:
            self.latest_packet_pts = packet.pts

        return False
