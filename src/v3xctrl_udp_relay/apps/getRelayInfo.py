import argparse
import json
import logging

from v3xctrl_udp_relay.Peer import Peer


def parse_args():
    parser = argparse.ArgumentParser(description="UDP Punch Client")
    parser.add_argument("server", help="Rendezvous server address")
    parser.add_argument("id", help="Session ID (required positional argument)")
    parser.add_argument("--port", default=8888, type=int, help="Rendezvous server port")
    parser.add_argument("--port-video", default=6666, type=int, help="Local video port")
    parser.add_argument("--port-control", default=6668, type=int, help="Local control port")
    parser.add_argument("--log", default="ERROR", help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). (default: ERROR")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    level_name = args.log.upper()
    level = getattr(logging, level_name, None)

    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {args.log}")

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    ports = {
        "video": args.port_video,
        "control": args.port_control
    }

    peer = Peer(args.server, args.port, args.id)
    peer_addresses = peer.setup("streamer", ports)

    video = peer_addresses["video"]
    control = peer_addresses["control"]

    print(json.dumps({
        "server": {
            "host": video[0]
        },
        "ports": {
            "video": video[1],
            "control": control[1]
        }
    }, indent=2))
