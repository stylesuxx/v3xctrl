import argparse
import threading

from punch import PunchPeer
from rpi_4g_streamer.Message import Ack

VIDEO_PORT = 16666
CONTROL_PORT = 16668

DEFAULT_RENDEZVOUS_SERVER = 'rendezvous.websium.at'
# RENDEZVOUS_SERVER = '192.168.1.100'
DEFAULT_RENDEZVOUS_PORT = 8888


class PunchServer(PunchPeer):
    def run(self):
        ports = {
            "video": VIDEO_PORT,
            "control": CONTROL_PORT
        }

        sockets, peer_info = self.setup("server", ports)

        ip = peer_info["video"].get_ip()
        vp, cp = peer_info["video"].get_video_port(), peer_info["control"].get_control_port()

        print(f"[✓] Ready to receive from client:")
        print(f"    VIDEO: {ip}:{vp}")
        print(f"    CONTROL: {ip}:{cp}")

        threading.Thread(target=self.video_listener, args=(sockets["video"],), daemon=True).start()
        self.control_listener(sockets["control"])

    def video_listener(self, sock):
        print(f"[V] Listening on {sock.getsockname()}")
        while True:
            data, addr = sock.recvfrom(2048)
            print(f"[V] from {addr}")

    def control_listener(self, sock):
        print(f"[C] Listening on {sock.getsockname()}")
        while True:
            _, addr = sock.recvfrom(1024)
            print(f"[C] from {addr}")
            sock.sendto(Ack().to_bytes(), addr)


def parse_args():
    parser = argparse.ArgumentParser(description="UDP Punch Server")
    parser.add_argument("id", help="Session ID (required positional argument)")
    parser.add_argument("--server", default=DEFAULT_RENDEZVOUS_SERVER, help="Rendezvous server address")
    parser.add_argument("--port", type=int, default=DEFAULT_RENDEZVOUS_PORT, help="Rendezvous server port")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    PunchServer(args.server, args.port, args.id).run()
