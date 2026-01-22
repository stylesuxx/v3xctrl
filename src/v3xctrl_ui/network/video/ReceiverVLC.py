import ctypes
import logging
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Callable, Optional

import numpy as np
import vlc

from v3xctrl_ui.network.video.Receiver import Receiver


class ReceiverVLC(Receiver):
    """VLC-based video receiver using SDP file for RTP stream."""

    def __init__(self, port: int, error_callback: Callable[[], None]) -> None:
        super().__init__(port, error_callback)

        self.instance: Optional[vlc.Instance] = None
        self.player: Optional[vlc.MediaPlayer] = None
        self.media: Optional[vlc.Media] = None

        # SDP file for RTP stream
        self.sdp_path = Path(tempfile.gettempdir()) / f"vlc_rtp_{self.port}.sdp"

        # Video format
        self.width = 0
        self.height = 0
        self.pitch = 0

        # Frame buffer
        self.frame_buffer: Optional[ctypes.Array] = None
        self.frame_ready = threading.Event()
        self.video_lock = threading.Lock()

        # VLC ready event
        self.vlc_ready = threading.Event()
        self.last_vlc_error = None

        # opaque pointer for VLC callbacks
        self.opaque = ctypes.c_void_p(0)

        # Frame timing
        self.last_frame_time = 0.0
        self.max_frame_age = 2.0  # seconds

    def _setup(self) -> None:
        """Setup VLC instance and SDP file."""
        self._write_sdp()

        vlc_args = [
            '--intf', 'dummy',
            '--no-audio',
            '--no-video-title-show',
            '--no-osd',
            '--verbose', '2',
            '--demux', 'sdp',
            '--network-caching', '50',
            '--live-caching', '50',
            '--clock-jitter', '0',
            '--clock-synchro', '0',
            '--rtp-max-src', '1',
            '--rtp-timeout', '5000000',
            '--drop-late-frames',
            '--no-skip-frames',
            '--avcodec-fast',
            '--avcodec-threads', '2',
            '--vout', 'dummy',
            '--no-video-deco',
            '--no-embedded-video',
        ]

        try:
            self.instance = vlc.Instance(vlc_args)
            logging.info(f"VLC instance created with {len(vlc_args)} options")
        except Exception as e:
            logging.error(f"Failed to create VLC instance: {e}")
            raise

    def _main_loop(self) -> None:
        """Main VLC receive loop using SDP file."""
        try:
            self.media = self.instance.media_new(str(self.sdp_path))
            if not self.media:
                raise RuntimeError(f"Failed to create media for SDP: {self.sdp_path}")

            self.player = self.instance.media_player_new()
            if not self.player:
                raise RuntimeError("Failed to create VLC media player")

            # Setup video callbacks
            self._setup_video_callbacks()

            # Event handling
            events = self.player.event_manager()
            events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_vlc_error)
            events.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_vlc_playing)
            events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_vlc_end)

            self.player.set_media(self.media)

            # Start playback
            logging.info(f"Starting VLC playback from SDP: {self.sdp_path}")
            result = self.player.play()
            if result != 0:
                raise RuntimeError(f"Failed to start VLC player: {result}")

            # Wait for VLC to signal format ready
            if not self.vlc_ready.wait(timeout=10.0):
                raise RuntimeError("Timeout waiting for VLC video format")

            logging.info(f"Video format ready: {self.width}x{self.height}")

            # Main processing loop
            last_stats_time = time.monotonic()
            while self.running.is_set():
                if self.last_vlc_error:
                    logging.error(f"VLC error: {self.last_vlc_error}")
                    self.keep_alive()
                    break

                self._process_frames()

                current_time = time.monotonic()
                if current_time - last_stats_time >= self.log_interval:
                    self._log_stats_if_needed()
                    last_stats_time = current_time

                time.sleep(0.001)

        except Exception as e:
            logging.exception(f"Error in VLC main loop: {e}")
            self.keep_alive()

    def _setup_video_callbacks(self) -> None:
        """Setup VLC video callbacks using ctypes."""

        LOCK_CB = ctypes.CFUNCTYPE(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
        )
        UNLOCK_CB = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
        )
        DISPLAY_CB = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)
        FORMAT_CB = ctypes.CFUNCTYPE(
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint)
        )

        self.lock_cb = LOCK_CB(self._lock_callback)
        self.unlock_cb = UNLOCK_CB(self._unlock_callback)
        self.display_cb = DISPLAY_CB(self._display_callback)
        self.format_cb = FORMAT_CB(self._format_callback)

        self.player.video_set_callbacks(
            self.lock_cb,
            self.unlock_cb,
            self.display_cb,
            self.opaque
        )
        self.player.video_set_format_callbacks(self.format_cb, None)

    def _format_callback(self, chroma, width, height, pitches, lines):
        w = width[0]
        h = height[0]
        self.width, self.height = w, h
        self.pitch = w * 4

        chroma[0] = b'RV32'
        pitches[0] = self.pitch
        lines[0] = h

        buffer_size = self.pitch * h
        self.frame_buffer = (ctypes.c_ubyte * buffer_size)()

        self.vlc_ready.set()
        logging.info(f"VLC format callback: {w}x{h}, buffer {buffer_size} bytes")
        return 1

    def _lock_callback(self, opaque, planes):
        planes[0] = ctypes.cast(self.frame_buffer, ctypes.c_void_p)
        return None

    def _unlock_callback(self, opaque, picture, planes):
        self.frame_ready.set()

    def _display_callback(self, opaque, picture):
        pass

    def _process_frames(self) -> None:
        if self.frame_ready.wait(timeout=0.001):
            self.frame_ready.clear()
            if self.frame_buffer and self.width > 0 and self.height > 0:
                try:
                    current_time = time.monotonic()
                    if self.last_frame_time > 0:
                        frame_age = current_time - self.last_frame_time
                        if frame_age > self.max_frame_age:
                            logging.debug(f"Dropping frame {frame_age:.2f}s old")
                            return

                    with self.video_lock:
                        buffer_array = np.ctypeslib.as_array(self.frame_buffer)
                        expected_size = self.width * self.height * 4

                        if len(buffer_array) >= expected_size:
                            rgba_frame = buffer_array[:expected_size].reshape(
                                (self.height, self.width, 4)
                            )
                            rgb_frame = rgba_frame[:, :, :3].copy()
                            self.last_frame_time = current_time
                            self._update_frame(rgb_frame)
                            self.packet_count += 1
                        else:
                            self.empty_decode_count += 1
                except Exception as e:
                    logging.warning(f"Error processing VLC frame: {e}")
                    self.empty_decode_count += 1

    def _cleanup(self) -> None:
        try:
            if self.player:
                self.player.stop()
                self.player.release()
        except Exception as e:
            logging.warning(f"Error stopping VLC player: {e}")
        finally:
            self.player = None

        try:
            if self.media:
                self.media.release()
        except Exception as e:
            logging.warning(f"Error releasing VLC media: {e}")
        finally:
            self.media = None

        try:
            if self.instance:
                self.instance.release()
        except Exception as e:
            logging.warning(f"Error releasing VLC instance: {e}")
        finally:
            self.instance = None

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

        logging.info(f"SDP file created: {self.sdp_path}")

    def _on_vlc_error(self, event):
        self.last_vlc_error = "VLC encountered an error"
        logging.error("VLC error event received")

    def _on_vlc_playing(self, event):
        logging.info("VLC started playing")

    def _on_vlc_end(self, event):
        logging.info("VLC end of stream reached")
