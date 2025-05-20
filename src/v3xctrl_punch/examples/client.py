import argparse
import logging
import threading
import time
import socket

from v3xctrl_punch.PunchPeer import PunchPeer
from rpi_4g_streamer.Message import Syn

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
    def __init__(self, sockets, peer_info):
        self.peer_info = peer_info

        self.remote_ip = peer_info["video"].get_ip()
        self.remote_video_port = peer_info["video"].get_video_port()
        self.remote_control_port = peer_info["control"].get_control_port()

        #self.video_sock = self._bind_udp(LOCAL_BIND_PORTS["video"])
        #self.control_sock = self._bind_udp(LOCAL_BIND_PORTS["control"])

        self.video_sock = sockets["video"]
        self.control_sock = sockets["control"]

    def _bind_udp(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', port))

        return sock

    def run(self):
        threading.Thread(target=self.video_sender, daemon=True).start()
        threading.Thread(target=self.control_loop, daemon=True).start()

        while True:
            time.sleep(1)

    def video_sender(self):
        logging.info(f"[V] Sending from {self.video_sock.getsockname()} to {(self.remote_ip, self.remote_video_port)}")
        while True:
            self.video_sock.sendto(Syn().to_bytes(), (self.remote_ip, self.remote_video_port))
            logging.info(f"[V] to {self.remote_ip}:{self.remote_video_port}")
            time.sleep(1)

    def control_loop(self):
        def receiver():
            logging.info(f"[C] Listening on {self.control_sock.getsockname()}")
            while True:
                _, addr = self.control_sock.recvfrom(1024)
                logging.info(f"[C] from {addr[0]}:{addr[1]}")

        threading.Thread(target=receiver, daemon=True).start()

        logging.info(f"[C] Sending from {self.control_sock.getsockname()} to {(self.remote_ip, self.remote_control_port)}")
        while True:
            self.control_sock.sendto(Syn().to_bytes(), (self.remote_ip, self.remote_control_port))
            logging.info(f"[C] to {self.remote_ip}:{self.remote_control_port}")
            time.sleep(1)


def parse_args():
    parser = argparse.ArgumentParser(description="UDP Punch Client")
    parser.add_argument("id", help="Session ID (required positional argument)")
    parser.add_argument("--server", default=DEFAULT_RENDEZVOUS_SERVER, help="Rendezvous server address")
    parser.add_argument("--port", type=int, default=DEFAULT_RENDEZVOUS_PORT, help="Rendezvous server port")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Step 1: Punch holes and get peer info
    punch = PunchPeer(args.server, args.port, args.id)
    sockets, peer_info = punch.setup("client", LOCAL_BIND_PORTS)

    # Step 2: Start client logic with freshly bound sockets
    TestClient(sockets, peer_info).run()
