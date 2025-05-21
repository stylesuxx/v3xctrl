import argparse
import logging
import threading
import time

from v3xctrl_punch.PunchPeer import PunchPeer
from v3xctrl_punch.helper import control_loop, bind_udp

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


class TestServer:
    def __init__(self, sockets, addrs):
        #self.video_sock = bind_udp(LOCAL_BIND_PORTS['video'])
        self.control_sock = bind_udp(LOCAL_BIND_PORTS['control'])

        self.video_sock = sockets["video"]
        #self.control_sock = sockets["control"]

        self.remote_video_addr = addrs["video"]
        self.remote_control_addr = addrs["control"]

    def run(self):
        # threading.Thread(target=self.video_listener, daemon=True, name="VideoListener").start()
        threading.Thread(target=control_loop, args=(self.control_sock, self.remote_control_addr), daemon=True, name="ControlListener").start()

        while True:
            time.sleep(1)

    def video_listener(self):
        logging.info(f"[V] Listening on {self.video_sock.getsockname()}")
        while True:
            _, addr = self.video_sock.recvfrom(2048)
            logging.info(f"[V] from {addr}")


def parse_args():
    parser = argparse.ArgumentParser(description="UDP Punch Server")
    parser.add_argument("id", help="Session ID (required positional argument)")
    parser.add_argument("--server", default=DEFAULT_RENDEZVOUS_SERVER, help="Rendezvous server address")
    parser.add_argument("--port", type=int, default=DEFAULT_RENDEZVOUS_PORT, help="Rendezvous server port")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Step 1: Punch holes
    peer = PunchPeer(args.server, args.port, args.id)
    sockets, _, addrs = peer.setup("server", LOCAL_BIND_PORTS)

    # Step 2: Listen for incoming client data
    TestServer(sockets, addrs).run()
