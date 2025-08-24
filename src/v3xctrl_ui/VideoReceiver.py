from collections import deque
import logging
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Callable

import av


class VideoReceiver(threading.Thread):
    def __init__(
        self,
        port: int,
        error_callback: Callable[[], None]
    ) -> None:
        super().__init__()

        self.port = port
        self.error_callback = error_callback

        self.running = threading.Event()
        self.frame_lock = threading.Lock()
        self.frame = None

        self.history: deque[float] = deque(maxlen=100)

        self.sdp_path = Path(tempfile.gettempdir()) / f"rtp_{self.port}.sdp"
        self.container = None

        self.container_lock = threading.Lock()
        self.thread_count = str(min(os.cpu_count(), 4))

        # Frame monitoring
        self.packet_count = 0
        self.decoded_frame_count = 0
        self.empty_decode_count = 0
        self.last_log_time = 0.0
        self.log_interval = 10.0  # Log every 10 seconds

    def run(self) -> None:
        self.running.set()

        self._write_sdp()

        options = {
            "fflags": "nobuffer",
            "protocol_whitelist": "file,crypto,data,udp,rtp",
            # The following options do not seem to work when passed as options
            # "timeout": "3000000",
            # "stimeout": "3000000",
            # "rw_timeout": "3000000",
            # "analyzeduration": "1000000",
            # "probesize": "2048"
        }

        while self.running.is_set():
            while self.running.is_set():
                try:
                    """
                    NOTE: It takes a while for opening the container, av will
                          not respect any timeouts at this point unfortunately.
                          Even when no stream is running, there will be a
                          container but the demux will fail further downstream.
                    """
                    with self.container_lock:
                        self.container = av.open(
                            f"{self.sdp_path}",
                            format="sdp",
                            options=options
                        )
                    break
                except av.AVError as e:
                    logging.warning(f"av.open() failed: {e}")
                    time.sleep(0.5)

            if self.container:
                stream = self.container.streams.video[0]
                stream.codec_context.thread_type = "AUTO"
                stream.codec_context.options = {
                    "threads": self.thread_count,
                    "flags": "low_delay",
                    "flags2": "fast"
                }

                try:
                    while self.running.is_set():
                        if self.container:
                            for packet in self.container.demux(stream):
                                if not self.running.is_set():
                                    break

                                self.packet_count += 1
                                decoded_frames = list(packet.decode())
                                if decoded_frames:
                                    for frame in decoded_frames:
                                        rgb_frame = frame.to_ndarray(format="rgb24")
                                        with self.frame_lock:
                                            self.frame = rgb_frame

                                        self.history.append(time.monotonic())
                                        self.decoded_frame_count += 1
                                else:
                                    self.empty_decode_count += 1

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
                    self.error_callback()

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

    def _log_stats_if_needed(self) -> None:
        current_time = time.monotonic()
        if current_time - self.last_log_time >= self.log_interval:
            if self.packet_count > 0:
                drop_rate = (self.empty_decode_count / self.packet_count) * 100

                time_elapsed = current_time - self.last_log_time if self.last_log_time > 0 else self.log_interval
                avg_fps = round(self.decoded_frame_count / time_elapsed) if time_elapsed > 0 else 0

                logging.info(
                    f"frames={self.decoded_frame_count}, "
                    f"empty_decodes={self.empty_decode_count}, "
                    f"drop_rate={drop_rate:.1f}%, avg_fps={avg_fps}"
                )

            # Reset for next interval
            self.packet_count = 0
            self.empty_decode_count = 0
            self.decoded_frame_count = 0

            self.last_log_time = current_time

    def stop(self) -> None:
        self.running.clear()
        if self.is_alive():
            self.join(timeout=5.0)

        with self.container_lock:
            if self.container:
                try:
                    self.container.close()
                except Exception as e:
                    logging.warning(f"Container close failed during stop: {e}")
                finally:
                    self.container = None

        try:
            if self.sdp_path.exists():
                self.sdp_path.unlink()
        except Exception as e:
            logging.warning(f"SDP file cleanup failed: {e}")

    def _write_sdp(self) -> None:
        sdp_text = f"""\
v=0
o=- 0 0 IN IP4 127.0.0.1
s=RTP Stream
c=IN IP4 0.0.0.0
t=0 0
m=video {self.port} RTP/AVP 96
a=rtpmap:96 H264/90000
a=recvonly
"""
        with open(self.sdp_path, "w", newline="\n") as f:
            f.write(sdp_text)
            f.flush()
            os.fsync(f.fileno())
