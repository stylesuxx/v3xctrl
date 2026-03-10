import logging
import os
from pathlib import Path
import tempfile
import threading
import time
from collections.abc import Callable

import av

from v3xctrl_ui.network.video.Receiver import Receiver
from v3xctrl_ui.network.video.UdpVideoProxy import UdpVideoProxy


class ReceiverPyAV(Receiver):
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
        relay_address: tuple[str, int] | None = None
    ) -> None:
        super().__init__(
            port,
            keep_alive,
            log_interval,
            history_size,
            max_frame_age_ms,
            render_ratio
        )

        self.relay_address = relay_address
        self._proxy: UdpVideoProxy | None = None

        self.container = None
        self.sdp_path = Path(tempfile.gettempdir()) / f"rtp_{self.port}.sdp"
        self.container_lock = threading.Lock()
        self.thread_count = str(min(os.cpu_count() or 1, 4))

        self.latest_packet_pts = None
        self.consecutive_old_frames = 0
        self.max_consecutive_old_frames = 60

        self.container_options = {
            "fflags": "nobuffer+flush_packets+discardcorrupt+nofillin",
            "protocol_whitelist": "file,udp,rtp",
            "analyzeduration": "1",
            "probesize": "32",
            "rw_timeout": "5000000",  # timeout for demux read operations (in us)
        }

        self.codec_options = {
            "threads": self.thread_count,
            "flags": "low_delay",
            "flags2": "fast"
        }

    def _setup(self) -> None:
        """Setup UDP proxy (if relay) and SDP file."""
        if self.relay_address:
            self._proxy = UdpVideoProxy(self.port, self.relay_address)
            if self._proxy.start_proxy():
                logging.info(
                    f"UDP video proxy active: :{self.port} -> "
                    f"localhost:{self._proxy.local_port}"
                )
            else:
                logging.warning(
                    "UDP video proxy failed to start, "
                    "falling back to direct port"
                )
                self._proxy = None

        self._write_sdp()

    def _close_container(self) -> None:
        with self.container_lock:
            if self.container is not None:
                try:
                    self.container.close()
                except Exception as e:
                    logging.warning(f"Container close failed: {e}")
                finally:
                    self.container = None

    def _refresh_local_port(self) -> None:
        """Find a new local port for the proxy and rewrite the SDP file.

        On Windows, ffmpeg's internal UDP socket may not be released
        immediately after container.close(). Using a fresh port on each
        reconnection attempt avoids binding conflicts that cause
        AVERROR_INVALIDDATA failures.
        """
        if not self._proxy:
            return

        new_port = UdpVideoProxy._find_free_local_port()
        if new_port == 0:
            logging.warning("Failed to find a new local port for proxy")
            return

        self._proxy.update_forward_port(new_port)
        self._write_sdp()
        logging.debug(f"Refreshed local forward port to {new_port}")

    def _main_loop(self) -> None:
        while self.running.is_set():
            container = None
            while self.running.is_set():
                try:
                    start_time = time.monotonic()
                    container = av.open(
                        str(self.sdp_path),
                        format="sdp",
                        options=self.container_options,
                        timeout=5
                    )
                    open_time = time.monotonic() - start_time
                    logging.info(f"Container opened in {open_time:.3f}s")

                    with self.container_lock:
                        self.container = container
                        self.latest_packet_pts = None
                        self.consecutive_old_frames = 0

                    break

                except av.AVError as e:
                    if self._proxy:
                        logging.warning(
                            f"av.open() failed: {e} "
                            f"(proxy mode, local_port={self._proxy.local_port}, "
                            f"received={self._proxy.packets_received}, "
                            f"forwarded={self._proxy.packets_forwarded})"
                        )
                    else:
                        logging.warning(
                            f"av.open() failed: {e} "
                            f"(direct mode, port={self.port})"
                        )
                    self._refresh_local_port()
                    time.sleep(0.5)

            if container is None:
                continue

            stream = container.streams.video[0]
            stream.codec_context.thread_type = "AUTO"
            stream.codec_context.options = self.codec_options

            consecutive_decode_errors = 0

            try:
                for packet in container.demux(stream):
                    if not self.running.is_set():
                        break

                    self.packet_count += 1

                    if self._should_drop_packet_by_age(packet, stream):
                        self.dropped_old_frames += 1
                        self.consecutive_old_frames += 1

                        # Force restart if too many consecutive old frames
                        if self.consecutive_old_frames > self.max_consecutive_old_frames:
                            logging.warning(
                                f"Dropped {self.consecutive_old_frames} consecutive old frames, "
                                f"forcing container restart"
                            )
                            break

                        continue

                    self.consecutive_old_frames = 0

                    try:
                        decode_start = time.monotonic()
                        decoded_frames = list(packet.decode())
                    except av.AVError as e:
                        consecutive_decode_errors += 1
                        if consecutive_decode_errors >= 30:
                            logging.warning(
                                f"Too many consecutive decode errors "
                                f"({consecutive_decode_errors}), restarting container"
                            )
                            break
                        logging.debug(f"Decode error (skipping packet): {e}")
                        continue

                    consecutive_decode_errors = 0

                    if decoded_frames:
                        decode_duration = (time.monotonic() - decode_start) / len(decoded_frames)
                        for frame in decoded_frames:
                            rgb_frame = frame.to_ndarray(format="rgb24")
                            self._update_frame(rgb_frame, decode_duration)
                    else:
                        self.dropped_empty_frames += 1

                    self._log_stats_if_needed()

            except av.AVError as e:
                logging.warning(f"Stream demux error: {e}")

            except Exception as e:
                logging.exception(f"Unexpected error in receiver thread: {e}")

            finally:
                with self.frame_lock:
                    self.frame = None
                    self.frame_buffer.clear()

                self._close_container()

                # Send keep-alive to maintain NAT hole when stream ends/fails.
                # When the proxy is active it handles heartbeats continuously,
                # so the transient-socket callback is not needed.
                if not self._proxy:
                    self.keep_alive()

    def _cleanup(self) -> None:
        """Cleanup container, proxy, and SDP file."""
        self._close_container()

        if self._proxy:
            self._proxy.stop()
            self._proxy.join(timeout=2.0)
            self._proxy = None

        try:
            if self.sdp_path.exists():
                self.sdp_path.unlink()
        except Exception as e:
            logging.warning(f"SDP file cleanup failed: {e}")

    def _write_sdp(self) -> None:
        """Write SDP file for RTP stream."""
        if self._proxy:
            listen_port = self._proxy.local_port
            listen_addr = "127.0.0.1"
        else:
            listen_port = self.port
            listen_addr = "0.0.0.0"

        sdp_text = f"""\
v=0
o=- 0 0 IN IP4 127.0.0.1
s=RTP Stream
c=IN IP4 {listen_addr}
t=0 0
m=video {listen_port} RTP/AVP 96
a=rtpmap:96 H264/90000
a=rtcp-fb:96 nack
a=rtcp-fb:96 nack pli
a=recvonly
"""
        with open(self.sdp_path, "w", newline="\n") as f:
            f.write(sdp_text)
            f.flush()
            os.fsync(f.fileno())

        logging.debug(
            f"SDP written: {self.sdp_path} "
            f"(listen={listen_addr}:{listen_port})"
        )

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
