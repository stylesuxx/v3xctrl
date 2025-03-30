import av
from collections import deque
import logging
import socket
import threading
import time


class VideoReceiver(threading.Thread):
    def __init__(self, port: int):
        super().__init__()

        self.port = port
        self.frame_lock = threading.Lock()

        self.running = threading.Event()

        self.decoder = None
        self.frame = None
        self.sock = None

        self.average_window = 30
        self.frame_times = deque(maxlen=self.average_window)

        self.history = deque(maxlen=300)

        self.last_frame_time = time.time()
        self.frame_timeout = 3.0

    def _init_decoder(self):
        self.decoder = av.CodecContext.create("h264", "r")

    def _init_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.port))
        self.sock.settimeout(0.2)

        logging.debug(f"Receiver listening on UDP port {self.port}...")

    def run(self):
        self._init_decoder()
        self._init_socket()

        self.running.set()
        while self.running.is_set():
            now = time.time()
            try:
                data, _ = self.sock.recvfrom(65536)
            except socket.timeout:
                if now - self.last_frame_time > self.frame_timeout:
                    logging.warning("Timeout detected.")
                    with self.frame_lock:
                        self.frame = None
                self.history.append(0.0)
                continue
            except OSError:
                if not self.running.is_set():
                    break
                raise

            try:
                packet = av.packet.Packet(data)
                frames = self.decoder.decode(packet)
            except av.AVError as e:
                logging.warning(f"Decoder error: {e}")
                continue

            for frame in frames:
                img = frame.to_ndarray(format="rgb24")
                with self.frame_lock:
                    self.frame = img
                    self.last_frame_time = now

            self.frame_times.append(now)
            if len(self.frame_times) == self.average_window:
                duration = self.frame_times[-1] - self.frame_times[0]
                if duration > 0:
                    video_fps = (len(self.frame_times) - 1) / duration
                    self.history.append(video_fps)

    def stop(self):
        self.running.clear()
        self.sock.close()
