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
        print("--- UDP hole duration test (CLIENT) ---")
        BUFFER_SIZE = 1024
        READY_MARKER = b"READY"
        CONFIRM_MARKER = b"CONFIRM"
        DONE_MARKER = b"DONE"

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
            print("Establishing UDP hole punch...", end='', flush=True)
            client_socket.settimeout(5)
            ready = False
            max_attempts = 5

            for _attempt in range(max_attempts):
                try:
                    client_socket.sendto(READY_MARKER, self.address)
                    data, _ = client_socket.recvfrom(BUFFER_SIZE)
                    if data == READY_MARKER:
                        ready = True
                        print(" OK")
                        break
                except socket.timeout:
                    print(".", end='', flush=True)

            if not ready:
                print(" FAILED")
                print("Could not establish UDP hole punch connection")
                return

            print("\nStarting duration test...")
            timeout_value = self.min_timeout
            last_successful_timeout = 0

            while timeout_value <= self.max_timeout:
                confirmed = False
                max_request_attempts = 3

                # Retry sending timeout request until confirmed
                for attempt in range(max_request_attempts):
                    # Send timeout request
                    client_socket.sendto(struct.pack("d", timeout_value), self.address)

                    # Wait for confirmation with short timeout
                    client_socket.settimeout(2)
                    try:
                        data, _ = client_socket.recvfrom(BUFFER_SIZE)
                        if data == CONFIRM_MARKER:
                            confirmed = True
                            break
                        elif data == DONE_MARKER:
                            # Late DONE from previous test, ignore and keep waiting
                            continue
                        else:
                            print(f"\n! Unexpected response for timeout {timeout_value:.2f}: {data}")
                            return

                    except socket.timeout:
                        if attempt < max_request_attempts - 1:
                            print(".", end='', flush=True)
                        continue

                if not confirmed:
                    print(f"\n! No confirmation received for timeout {timeout_value:.2f} after {max_request_attempts} attempts")
                    break

                # Drain any duplicate confirmations
                client_socket.settimeout(0.2)
                try:
                    while True:
                        data, _ = client_socket.recvfrom(BUFFER_SIZE)
                except socket.timeout:
                    pass

                # Wait for completion with extended timeout
                client_socket.settimeout(timeout_value + 10)
                try:
                    data, _ = client_socket.recvfrom(BUFFER_SIZE)

                    # Drain any duplicate DONE messages and late confirmations
                    client_socket.settimeout(0.5)
                    try:
                        while True:
                            client_socket.recvfrom(BUFFER_SIZE)
                    except socket.timeout:
                        pass

                    print(f"+ Received timeout response: {timeout_value:7.2f} OK")
                    last_successful_timeout = timeout_value
                    timeout_value += self.increment

                except socket.timeout:
                    print("")
                    print("--- Results ---")
                    print(f"Minimum hole lifetime: {last_successful_timeout:.2f}s")
                    print(f"Failed at: {timeout_value:.2f}s")
                    break


if __name__ == "__main__":
    test = SelfTestClient(HOST, PORT, args.increment, args.min_timeout, args.max_timeout)
    test.udp_hole_duration()
