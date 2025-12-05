import argparse
import socket
import struct


parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("host", help="The target IP address")
parser.add_argument("port", type=int, help="The target port number")
parser.add_argument(
    "--increment",
    type=int,
    default=30,
    help="Timeout increment in seconds (default: 10)"
)
parser.add_argument(
    "--min-timeout",
    type=int,
    default=30,
    help="Minimum timeout in seconds (default: 10)"
)
parser.add_argument(
    "--max-timeout",
    type=int,
    default=3600,
    help="Maximum timeout in seconds (default: 3600)"
)
args = parser.parse_args()

HOST = args.host
PORT = args.port


class SelfTestClient:
    def __init__(self, host: str, port: int, increment: int, min_timeout: int, max_timeout: int) -> None:
        self.host = host
        self.port = port
        self.address = (self.host, self.port)
        self.increment = increment
        self.min_timeout = min_timeout
        self.max_timeout = max_timeout

    def udp_hole_duration(self) -> None:
        print("--- Started UDP hole duration test ---")

        BUFFER_SIZE = 1024
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
            timeout_value = self.min_timeout

            while timeout_value <= self.max_timeout:
                client_socket.sendto(struct.pack("d", timeout_value), self.address)
                client_socket.settimeout(timeout_value + 5)

                try:
                    client_socket.recvfrom(BUFFER_SIZE)
                    print(f"+ Received timout response: {timeout_value:7.2f} OK")
                    timeout_value += self.increment

                except socket.timeout:
                    print("")
                    print("--- Results ---")
                    print(f"Minimum hole lifetime: {timeout_value:.2f}s")
                    break


if __name__ == "__main__":
    print(f"Connecting to {HOST}:{PORT} - check server for test results...")

    test = SelfTestClient(HOST, PORT, args.increment, args.min_timeout, args.max_timeout)
    test.udp_hole_duration()
