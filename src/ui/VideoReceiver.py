import av
from collections import deque
import logging
import threading
import time
import os
from pathlib import Path


# av.logging.set_level(av.logging.DEBUG)


class VideoReceiver(threading.Thread):
    def __init__(self, port: int):
        super().__init__()
        self.port = port
        self.running = threading.Event()
        self.frame_lock = threading.Lock()
        self.frame = None

        self.history = deque(maxlen=100)

        self.sdp_path = Path(f"/tmp/rtp_{self.port}.sdp")
        self.container = None

    def _write_sdp(self):
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

    def run(self):
        self.running.set()

        self._write_sdp()

        options = {
            "fflags": "nobuffer",
            "protocol_whitelist": "file,crypto,data,udp,rtp"
        }

        while self.running.is_set():
            while self.running.is_set():
                try:
                    self.container = av.open(str(self.sdp_path), format="sdp", options=options)
                    break
                except av.AVError as e:
                    logging.warning(f"av.open() failed: {e}")
                    time.sleep(0.5)

            if not self.container:
                return

            stream = self.container.streams.video[0]
            stream.codec_context.thread_type = "AUTO"
            stream.codec_context.options = {"threads": "2"}

            try:
                while self.running.is_set():
                    for packet in self.container.demux(stream):
                        if not self.running.is_set():
                            break

                        for frame in packet.decode():
                            img = frame.to_ndarray(format="rgb24")
                            with self.frame_lock:
                                self.frame = img

                            self.history.append(time.time())
            except av.AVError as e:
                logging.warning(f"Stream decode error: {e}")
            except Exception as e:
                logging.exception(f"Unexpected error in receiver thread: {e}")
            finally:
                try:
                    if self.container:
                        self.container.close()
                        self.container = None
                except Exception as e:
                    logging.warning(f"Container close failed: {e}")

    def stop(self):
        self.running.clear()
