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
    """

    def __init__(self, port: int, error_callback: Callable[[], None]) -> None:
        super().__init__()

        self.port = port
        self.error_callback = error_callback

        self.running = threading.Event()
        self.frame_lock = threading.Lock()
        self.frame: Optional[npt.NDArray[np.uint8]] = None

        # Frame monitoring
        self.history: deque[float] = deque(maxlen=100)
        self.packet_count = 0
        self.decoded_frame_count = 0
        self.dropped_old_frames = 0
        self.empty_decode_count = 0
        self.last_log_time = 0.0
        self.log_interval = 10.0

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

    def _update_frame(self, new_frame: npt.NDArray[np.uint8]) -> None:
        """Update current frame and history in thread-safe manner."""
        with self.frame_lock:
            self.frame = new_frame

        self.history.append(time.monotonic())
        self.decoded_frame_count += 1

    def _log_stats_if_needed(self) -> None:
        """Log statistics if interval has passed."""
        current_time = time.monotonic()
        if current_time - self.last_log_time >= self.log_interval:
            if self.packet_count > 0:
                dropped_total = self.empty_decode_count + self.dropped_old_frames
                drop_rate = (dropped_total / self.packet_count) * 100

                time_elapsed = self.log_interval
                if self.last_log_time > 0:
                    time_elapsed = current_time - self.last_log_time
                avg_fps = round(self.decoded_frame_count / time_elapsed) if time_elapsed > 0 else 0

                logging.info(
                    f"{self.__class__.__name__}: "
                    f"frames={self.decoded_frame_count}, "
                    f"empty_decodes={self.empty_decode_count}, "
                    f"dropped_old={self.dropped_old_frames}, "
                    f"drop_rate={drop_rate:.1f}%, avg_fps={avg_fps}"
                )

            # Reset for next interval
            self.packet_count = 0
            self.empty_decode_count = 0
            self.decoded_frame_count = 0
            self.dropped_old_frames = 0
            self.last_log_time = current_time
