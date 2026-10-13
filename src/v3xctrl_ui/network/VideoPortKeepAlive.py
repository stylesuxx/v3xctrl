import logging
import socket
import threading
import time

from v3xctrl_control.message import Heartbeat

logger = logging.getLogger(__name__)

# Refreshes the NAT mapping of the video port, and in spectator mode it is the only
# traffic the viewer sends to the relay, so it also carries the spectator
# registration. The relay drops a spectator after PacketRelay.SPECTATOR_TIMEOUT (30 s)
# without a packet, so three heartbeats fit into that window and two may go missing.
INTERVAL_STREAMING_S = 10.0


class VideoPortKeepAlive(threading.Thread):
    """
    Send periodic Heartbeat packets from the video port to the relay
    to prevent the NAT mapping from expiring.
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
        the video port permanently - ffmpeg (PyAV) needs exclusive
        access to the port while its container is open.
        """
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.video_port))
            sock.sendto(Heartbeat().to_bytes(), self.relay_address)
        except Exception as e:
            logger.debug(f"Video port keep-alive heartbeat skipped on port {self.video_port}: {e}")
        finally:
            if sock:
                sock.close()

    def run(self) -> None:
        self._running.set()
        logger.info(f"Video port keep-alive started on port {self.video_port}")

        while self._running.is_set():
            self._send_heartbeat()

            # Use short sleeps so stop() is responsive
            interval = INTERVAL_STREAMING_S
            waited = 0.0
            while waited < interval and self._running.is_set():
                time.sleep(min(1.0, interval - waited))
                waited += 1.0

        logger.info("Video port keep-alive stopped")
