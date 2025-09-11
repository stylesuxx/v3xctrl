from abc import ABC, abstractmethod
from collections import deque
import logging
import threading
import time
from typing import Callable, Optional

import numpy as np
import numpy.typing as npt


class VideoReceiver(ABC, threading.Thread):
    """
    Abstract base class for video receivers.

    Provides an interface to quickly implement different video receiver
    backends.

    Top priority with any video receiver is to show the user the most recent
    frame as quickly is possible.

    NOTES:
    The transmitter is sending out encoded frames via UDP as fast as possible,
    with a set frame-rate (30fps).

    Those frames are then decoded by the receiver, there is a couple of things
    to consider:
    * Frames arrive to late: UDP does not guarantee order, so due to routing it
      might be, that frames simply arrive out of order. Obviously we are not
      interested in late frames - we want the most current image.

    * Frames arrive in bursts: There might be 30 frames arriving per second in
      total, but when they arrive in bursts, we can not render them fast enough
      with a fixed framerate and thus some of them might need to be dropped.

      Example: Consider that 15 frames arrive in the first 10ms of a second time
               interval and 15 frames arrive in the last 10ms of a second time
               interval. So we have actually received 30FPS. But effectively
               rendered we only did 2 (considering a render loop of 60FPS).

               Timeline:
               0ms   : No frame to render
               *10ms : 15 frames arrive in a burst and are decoded
               16ms  : We render the last available frame (14 frames dropped)
               32ms  : We render the previous frame (frame 15)
               ...
               320ms : Still no new frame (we render frame 15 again)
               ...
               500ms : Still no new frame (we render frame 15 again)
               ...
               983ms : Still no new frame (we render frame 15 again)
               *990ms: 15 frames arrive in a burst and are decoded
               1000ms: We render the last available frame (14 frames dropped)

               So although 30 frames have been received and decoded in this
               second, we could effectively only display 2!

    * Frames can not be decoded: Data arrives but can for one reason or another
      not be decoded.

    So a frame might not be displayed for one of three reasons:
    1. It was broken
    2. It arrived too late (previous frames have already been shown)
    3. It arrived in a burst
    """

    def __init__(self, port: int, error_callback: Callable[[], None]) -> None:
        super().__init__()

        self.port = port
        self.error_callback = error_callback

        self.running = threading.Event()
        self.frame_lock = threading.Lock()
        self.frame: Optional[npt.NDArray[np.uint8]] = None

        # Frame monitoring
        self.render_history: deque[float] = deque(maxlen=100)

        self.packet_count = 0
        self.decoded_frame_count = 0
        self.rendered_frame_count = 0

        self.dropped_empty_frames = 0
        self.dropped_old_frames = 0
        self.dropped_burst_frames = 0

        self.last_log_time = 0.0
        self.log_interval = 10.0
        self.frame_fetched = False

    @abstractmethod
    def _setup(self) -> None:
        """Setup resources (SDP files, containers, etc.)."""
        pass

    @abstractmethod
    def _main_loop(self) -> None:
        """Main receive/decode loop. Should respect self.running.is_set()."""
        pass

    @abstractmethod
    def _cleanup(self) -> None:
        """Cleanup resources."""
        pass

    def stop(self) -> None:
        """Stop the receiver thread."""
        self.running.clear()
        if self.is_alive():
            self.join(timeout=5.0)

        try:
            self._cleanup()
        except Exception as e:
            logging.exception(f"Error during stop cleanup: {e}")

    def run(self) -> None:
        """Template method that calls abstract methods."""
        self.running.set()

        try:
            self._setup()
            self._main_loop()

        except Exception as e:
            # Catch and log all exceptions to prevent them from becoming
            # unhandled thread exceptions
            logging.exception(f"Error in {self.__class__.__name__}: {e}")

        finally:
            try:
                self._cleanup()

            except Exception as e:
                # Log cleanup errors but don't let them crash the receiver
                logging.exception(f"Error during cleanup: {e}")

    def get_frame(self) -> Optional[npt.NDArray[np.uint8]]:
        if not self.frame_fetched:
            self.frame_fetched = True
            self.render_history.append(time.monotonic())
            self.rendered_frame_count += 1

        with self.frame_lock:
            return self.frame

    def _update_frame(self, new_frame: npt.NDArray[np.uint8]) -> None:
        """Update current frame and history in thread-safe manner."""
        with self.frame_lock:
            if self.frame is not None and not self.frame_fetched:
                self.dropped_burst_frames += 1

            self.frame = new_frame
            self.frame_fetched = False

        self.decoded_frame_count += 1

    def _log_stats_if_needed(self) -> None:
        """Log statistics if interval has passed."""
        current_time = time.monotonic()
        if current_time - self.last_log_time >= self.log_interval:
            if self.packet_count > 0:
                dropped_total = self.dropped_empty_frames + self.dropped_old_frames + self.dropped_burst_frames
                drop_rate = (dropped_total / self.packet_count) * 100

                time_elapsed = self.log_interval
                if self.last_log_time > 0:
                    time_elapsed = current_time - self.last_log_time
                avg_decoded_fps = round(self.decoded_frame_count / time_elapsed) if time_elapsed > 0 else 0
                avg_rendered_fps = round(self.rendered_frame_count / time_elapsed) if time_elapsed > 0 else 0

                logging.info(
                    f"{self.__class__.__name__}: "
                    f"frames={self.decoded_frame_count}, "
                    f"dropped_empty={self.dropped_empty_frames}, "
                    f"dropped_old={self.dropped_old_frames}, "
                    f"dropped_burst={self.dropped_burst_frames}, "
                    f"drop_rate={drop_rate:.1f}%, "
                    f"avg_decoded_fps={avg_decoded_fps}, "
                    f"avg_rendered_fps={avg_rendered_fps}"
                )

            # Reset for next interval
            self.packet_count = 0
            self.dropped_empty_frames = 0
            self.decoded_frame_count = 0
            self.rendered_frame_count = 0
            self.dropped_old_frames = 0
            self.dropped_burst_frames = 0
            self.last_log_time = current_time
