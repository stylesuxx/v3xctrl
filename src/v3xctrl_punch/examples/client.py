import argparse
import logging
import threading
import time

from v3xctrl_punch.PunchPeer import PunchPeer
from rpi_4g_streamer.Message import Syn, Heartbeat

from v3xctrl_punch.helper import control_loop, bind_udp

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


class TestClient:
    def __init__(self, sockets, addrs):
        #self.video_sock = sockets["video"]
        self.video_sock = bind_udp(LOCAL_BIND_PORTS['video'])
        self.control_sock = bind_udp(LOCAL_BIND_PORTS['control'])

        self.remote_video_addr = addrs["video"]
        self.remote_control_addr = addrs["control"]

    def run(self):
        threading.Thread(target=self.video_sender, daemon=True).start()
        threading.Thread(target=control_loop, args=(self.control_sock, self.remote_control_addr), daemon=True).start()

        while True:
            time.sleep(1)

    def video_sender(self):
        logging.info(f"[V] Sending from {self.video_sock.getsockname()} to {self.remote_video_addr}")
        while True:
            self.video_sock.sendto(Heartbeat().to_bytes(), self.remote_video_addr)
            logging.info(f"[V] to {self.remote_video_addr}")
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
    sockets, _, addrs = punch.setup("client", LOCAL_BIND_PORTS)

    TestClient(sockets, addrs).run()
