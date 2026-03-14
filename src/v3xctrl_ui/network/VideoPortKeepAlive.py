import logging
import socket
import threading
import time

from v3xctrl_control.message import Heartbeat

# Keepalive interval when video is not running (NAT hole punch)
INTERVAL_IDLE_S = 1.0

# Keepalive interval during active streaming (NAT mapping refresh)
INTERVAL_STREAMING_S = 30.0


class VideoPortKeepAlive(threading.Thread):
    """
    Send periodic Heartbeat packets from the video port to the relay.

    Uses a faster interval when video is not yet running (to punch the NAT
    hole) and a slower interval during active streaming (to prevent the
    mapping from expiring).
    """

    def __init__(
        self,
        video_port: int,
        relay_host: str,
        relay_port: int,
    ) -> None:
        super().__init__(daemon=True)
        self.video_port = video_port
        self.relay_address = (relay_host, relay_port)
        self._running = threading.Event()

    def stop(self) -> None:
        self._running.clear()

    def _send_heartbeat(self) -> None:
        """Create a transient socket to send one heartbeat.

        The socket is opened and closed each time so it does not hold
        the video port permanently — ffmpeg (PyAV) needs exclusive
        access to the port while its container is open.
        """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.video_port))
            sock.sendto(Heartbeat().to_bytes(), self.relay_address)
        except Exception as e:
            logging.debug(
                f"Video port keep-alive heartbeat skipped on port "
                f"{self.video_port}: {e}"
            )
        finally:
            if sock:
                sock.close()

    def run(self) -> None:
        self._running.set()
        logging.info(
            f"Video port keep-alive started on port {self.video_port}"
        )

        while self._running.is_set():
            self._send_heartbeat()

            # Use short sleeps so stop() is responsive
            interval = INTERVAL_STREAMING_S
            waited = 0.0
            while waited < interval and self._running.is_set():
                time.sleep(min(1.0, interval - waited))
                waited += 1.0

        logging.info("Video port keep-alive stopped")
