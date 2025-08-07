import argparse
import logging
import threading
import time

from v3xctrl_punch.examples.TestPeer import TestPeer
from v3xctrl_punch.PunchPeer import PunchPeer

logging.basicConfig(
    level="DEBUG",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

LOCAL_BIND_PORTS = {
    "video": 16666,
    "control": 16668
}

DEFAULT_RENDEZVOUS_SERVER = 'rendezvous.websium.at'
DEFAULT_RENDEZVOUS_PORT = 8888


class TestServer(TestPeer):
    def run(self) -> None:
        threading.Thread(
            target=self.video_listener,
            daemon=True,
            name="VideoListener"
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

    def video_listener(self) -> None:
        logging.info(f"[V] Listening on {self.video_sock.getsockname()}")
        while True:
            _, addr = self.video_sock.recvfrom(2048)
            addr_formatted = f"{addr[0]}:{addr[1]}"
            logging.info(f"[V] from {addr_formatted}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UDP Punch Server")
    parser.add_argument("id", help="Session ID (required positional argument)")
    parser.add_argument("--server", default=DEFAULT_RENDEZVOUS_SERVER, help="Rendezvous server address")
    parser.add_argument("--port", type=int, default=DEFAULT_RENDEZVOUS_PORT, help="Rendezvous server port")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Step 1: Punch holes
    peer = PunchPeer(args.server, args.port, args.id)
    peerAddresses = peer.setup("server", LOCAL_BIND_PORTS)

    # Step 2: Listen for incoming client data
    TestServer(LOCAL_BIND_PORTS, peerAddresses).run()
