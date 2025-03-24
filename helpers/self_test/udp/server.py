import argparse
import socket


parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("port", type=int, help="The target port number")
args = parser.parse_args()

PORT = args.port
HOST = "0.0.0.0"
BUFFER_SIZE = 8096


def udp_rtt_test():
    TIMEOUT = 60
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((HOST, PORT))
        sock.settimeout(TIMEOUT)

        data = b""
        try:
            while data == b"":
                data, addr = sock.recvfrom(BUFFER_SIZE)
                sock.sendto(data, addr)

            print(data.decode("utf-8"))

        except socket.timeout:
            print(f"Timeout occurred, no packages received after ${TIMEOUT} seconds")


if __name__ == "__main__":
    print(f"Waiting for UDP packets on {HOST}:{PORT}")
    udp_rtt_test()
