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


class SelfTestServer:
    def __init__(self, host: str, port: int, max_timeout: int) -> None:
        self.host = host
        self.port = port
        self.max_timeout = max_timeout

    def udp_hole_duration(self) -> None:
        print("--- UDP hole duration test ---")

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind((self.host, self.port))
            sock.settimeout(TIMEOUT)

            requested_timeout = 0
            previous_timeout = 0
            first_request = True
            try:
                while requested_timeout <= self.max_timeout:
                    data, addr = sock.recvfrom(BUFFER_SIZE)

                    # Complete previous line with OK if not first request
                    if not first_request:
                        print(" OK")
                        previous_timeout = requested_timeout

                    # Extract requested timeout (client sends as struct "d" - double)
                    requested_timeout = struct.unpack("d", data)[0]
                    print(f"+ Received timeout request: {requested_timeout:7.2f}", end='', flush=True)

                    # Wait and send response
                    time.sleep(requested_timeout)
                    sock.sendto(b"", addr)

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
