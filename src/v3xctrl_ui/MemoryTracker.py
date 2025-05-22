import tracemalloc
import time
import threading


class MemoryTracker:
    def __init__(self, interval=10, top=5, enable_log=True):
        """
        :param interval: Seconds between snapshots
        :param top: Number of top growing lines to report
        :param enable_log: Whether to print memory growth reports
        """
        self.interval = interval
        self.top = top
        self.enable_log = enable_log
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._baseline = None

    def start(self):
        tracemalloc.start()
        self._baseline = tracemalloc.take_snapshot()
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join()

    def _run(self):
        while not self._stop_event.is_set():
            time.sleep(self.interval)
            current = tracemalloc.take_snapshot()

            # Filter out tracemalloc-related frames
            current = current.filter_traces((
                tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
                tracemalloc.Filter(False, "<frozen importlib._bootstrap_external>"),
                tracemalloc.Filter(False, "*tracemalloc*"),
            ))

            self._baseline = self._baseline.filter_traces((
                tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
                tracemalloc.Filter(False, "<frozen importlib._bootstrap_external>"),
                tracemalloc.Filter(False, "*tracemalloc*"),
            ))

            stats = current.compare_to(self._baseline, 'lineno')

            if self.enable_log:
                print(f"[MemoryTracker] Top {self.top} memory growth lines since last snapshot:")
                for stat in stats[:self.top]:
                    print(f"  {stat}")

            self._baseline = current
