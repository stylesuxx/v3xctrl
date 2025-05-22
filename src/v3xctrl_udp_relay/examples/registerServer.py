import argparse
import logging

from v3xctrl_udp_relay.Peer import Peer

logging.basicConfig(
    level="DEBUG",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

LOCAL_BIND_PORTS = {
    "video": 6666,
    "control": 6668
}

DEFAULT_RENDEZVOUS_SERVER = 'rendezvous.websium.at'
DEFAULT_RENDEZVOUS_PORT = 8888


def parse_args():
    parser = argparse.ArgumentParser(description="UDP Punch Server")
    parser.add_argument("id", help="Session ID (required positional argument)")
    parser.add_argument("--server", default=DEFAULT_RENDEZVOUS_SERVER, help="Rendezvous server address")
    parser.add_argument("--port", type=int, default=DEFAULT_RENDEZVOUS_PORT, help="Rendezvous server port")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    peer = Peer(args.server, args.port, args.id)
    peer_addresses = peer.setup("server", LOCAL_BIND_PORTS)
