import argparse
import socket
import struct
import time
import os

parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("port", type=int, help="The target port number")
args = parser.parse_args()

PORT = args.port
HOST = "0.0.0.0"
BUFFER_SIZE = 4096


def speed_test_client_to_server():
    received_bytes = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, PORT))
        sock.listen(1)

        conn, addr = sock.accept()
        print(f"Connection from {addr}")

        start_time = time.time()
        with conn:
            while True:
                data = conn.recv(BUFFER_SIZE)
                if not data:
                    break
                received_bytes += len(data)

        end_time = time.time()
        duration = end_time - start_time
        speed_mbps = (received_bytes * 8) / (duration * 1000000)

        sock.close()

        print("--- Download Test Results (Client -> Server) ---")
        print(f"Received {received_bytes / (1024*1024):.2f} MB in {duration:.2f} seconds")
        print(f"Download speed: {speed_mbps:.2f} Mbps")


def speed_test_server_to_client():
    FILE_SIZE = 10 * 1024 * 1024  # 10MB
    data = os.urandom(FILE_SIZE)  # Generate 10MB of random data

    sent_bytes = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, PORT))
        sock.listen(1)

        conn, addr = sock.accept()
        print(f"Connection from {addr}")

        start_time = time.time()
        while sent_bytes < FILE_SIZE:
            chunk = data[sent_bytes:sent_bytes+BUFFER_SIZE]
            conn.sendall(chunk)
            sent_bytes += len(chunk)
        end_time = time.time()
        duration = end_time - start_time
        speed_mbps = (sent_bytes * 8) / (duration * 1000000)

        sock.close()

        print("--- Upload Test Results (Server -> Client) ---")
        print(f"Sent {sent_bytes / (1024*1024):.2f} MB in {duration:.2f} seconds")
        print(f"Upload speed: {speed_mbps:.2f} Mbps")


def udp_latency_server():
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


def udp_hole_duration():
    TIMEOUT_DURATION = 10  # Stop listening after 10 seconds

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((HOST, PORT))
        sock.settimeout(TIMEOUT_DURATION)

        requested_timeout = 0
        try:
            while True:
                data, addr = sock.recvfrom(BUFFER_SIZE)

                # Extract requested timeout (client sends as struct "d" - double)
                requested_timeout = struct.unpack("d", data)[0]
                print(f"Received timeout request: {requested_timeout:.2f} sec from {addr}")

                # Wait for the requested time
                time.sleep(requested_timeout)

                # Send response back to client
                sock.sendto(b"ping", addr)
                print(f"Sent response to {addr} after {requested_timeout:.2f} sec")
        except socket.timeout:
            print("No new request received from client.")
            print(f"Approximate hole duration: {requested_timeout}")


if __name__ == "__main__":
    print(f"# Server waiting on upload: {HOST}:{PORT}")
    speed_test_client_to_server()

    print(f"\n# Server waiting to download: {HOST}:{PORT}")
    speed_test_server_to_client()

    print(f"\n# UDP echo server listening on {HOST}:{PORT}")
    udp_latency_server()

    print(f"\n# UDP hole duration server listening on {HOST}:{PORT}")
    udp_hole_duration()
