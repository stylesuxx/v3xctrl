import argparse
import logging
import threading
import time

from v3xctrl_punch.examples.TestPeer import TestPeer
from v3xctrl_punch.PunchPeer import PunchPeer
from rpi_4g_streamer.Message import Heartbeat

logging.basicConfig(
    level="DEBUG",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

LOCAL_BIND_PORTS = {
    "video": 26666,
    "control": 26668
}

DEFAULT_RENDEZVOUS_SERVER = 'rendezvous.websium.at'
DEFAULT_RENDEZVOUS_PORT = 8888


class TestClient(TestPeer):
    def __init__(self, ports, addresses):
        super().__init__(ports, addresses)

        self.remote_video_addr_formatted = f"{self.remote_video_addr[0]}:{self.remote_video_addr[1]}"

    def run(self):
        threading.Thread(
            target=self.video_sender,
            daemon=True,
            name="VideoSender"
        ).start()
        threading.Thread(
            target=self.control_loop,
            args=(self.control_sock, self.remote_control_addr),
            daemon=True,
            name="ControlLoop"
        ).start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Exiting...")

    def video_sender(self):
        sock_name = self.video_sock.getsockname()
        sock_formatted = f"{sock_name[0]}:{sock_name[1]}"
        logging.info(f"[V] Sending from {sock_formatted} to {self.remote_video_addr_formatted}")
        while True:
            self.video_sock.sendto(Heartbeat().to_bytes(), self.remote_video_addr)
            logging.info(f"[V] to   {self.remote_video_addr_formatted}")
            time.sleep(1)


def parse_args():
    parser = argparse.ArgumentParser(description="UDP Punch Client")
    parser.add_argument("id", help="Session ID (required positional argument)")
    parser.add_argument("--server", default=DEFAULT_RENDEZVOUS_SERVER, help="Rendezvous server address")
    parser.add_argument("--port", type=int, default=DEFAULT_RENDEZVOUS_PORT, help="Rendezvous server port")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    punch = PunchPeer(args.server, args.port, args.id)
    peer_addresses = punch.setup("client", LOCAL_BIND_PORTS)

    TestClient(LOCAL_BIND_PORTS, peer_addresses).run()
