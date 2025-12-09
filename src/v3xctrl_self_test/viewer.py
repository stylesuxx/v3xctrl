import argparse
import socket
import struct
import time


parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("port", type=int, help="The target port number")
parser.add_argument(
    "--max-timeout",
    type=int,
    default=3600,
    help="Maximum timeout to accept before stopping (default: 3600s)"
)
args = parser.parse_args()

PORT = args.port
HOST = "0.0.0.0"
BUFFER_SIZE = 8096
TIMEOUT = 60

READY_MARKER = b"READY"
CONFIRM_MARKER = b"CONFIRM"
DONE_MARKER = b"DONE"


class SelfTestServer:
    def __init__(self, host: str, port: int, max_timeout: int) -> None:
        self.host = host
        self.port = port
        self.max_timeout = max_timeout

    def udp_hole_duration(self) -> None:
        print("--- UDP hole duration test (SERVER) ---")

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((self.host, self.port))
            sock.settimeout(TIMEOUT)

            print("Waiting for client connection...", end='', flush=True)
            ready = False
            while not ready:
                try:
                    data, addr = sock.recvfrom(BUFFER_SIZE)
                    if data == READY_MARKER:
                        sock.sendto(READY_MARKER, addr)
                        ready = True
                        print(f" OK ({addr[0]}:{addr[1]})")

                except socket.timeout:
                    print(".", end='', flush=True)
                    continue

            print("\nStarting duration test...")
            requested_timeout = 0
            previous_timeout = 0
            first_request = True
            try:
                while requested_timeout <= self.max_timeout:
                    data, addr = sock.recvfrom(BUFFER_SIZE)

                    if data == READY_MARKER:
                        sock.sendto(READY_MARKER, addr)
                        continue

                    # Complete previous line with OK if not first request
                    if not first_request:
                        print(" OK")
                        previous_timeout = requested_timeout

                    # Extract requested timeout (client sends as struct "d" - double)
                    requested_timeout = struct.unpack("d", data)[0]
                    print(f"+ Received timeout request: {requested_timeout:7.2f}", end='', flush=True)

                    # Send confirmation multiple times to ensure delivery
                    for _ in range(3):
                        sock.sendto(CONFIRM_MARKER, addr)
                        time.sleep(0.1)

                    # Wait and send completion response multiple times
                    time.sleep(requested_timeout)
                    for _ in range(3):
                        sock.sendto(DONE_MARKER, addr)
                        time.sleep(0.1)

                    first_request = False
            except socket.timeout:
                if not first_request:
                    print(" FAILED")

            print("")
            print("--- Results ---")
            print(f"Minimum hole lifetime: {previous_timeout:.2f}s")


if __name__ == "__main__":
    test = SelfTestServer(HOST, PORT, args.max_timeout)
    test.udp_hole_duration()
