import argparse
import logging
import signal
import sys

from v3xctrl_udp_relay.UDPRelayServer import UDPRelayServer


def main():
    parser = argparse.ArgumentParser(description="Start a UDP relay server.")
    parser.add_argument("ip", help="IP address to bind to")
    parser.add_argument("--port", type=int, default=8888, help="UDP port to bind to (default: 8888)")
    parser.add_argument("--log", default="ERROR",
                        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). (default: ERROR")
    parser.add_argument('--db', '--db-path', dest='db_path', default='relay.db',
                        help='Path to SQLite database (default: relay.db)')
    args = parser.parse_args()

    level_name = args.log.upper()
    level = getattr(logging, level_name, None)

    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {args.log}")

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    server = UDPRelayServer(args.ip, args.port, args.db_path)

    def shutdown(signum, frame):
        logging.info("Shutting down UDPRelayServer...")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    server.start()
    server.join()


if __name__ == "__main__":
    main()
