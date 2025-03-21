import argparse
import socket
import struct
import time


parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("port", type=int, help="The target port number")
args = parser.parse_args()

PORT = args.port
HOST = "0.0.0.0"
BUFFER_SIZE = 8096


def format_speed(bytes_transmitted: int, duration: float) -> str:
    bps = (bytes_transmitted * 8) / duration

    units = ["bps", "Kbps", "Mbps", "Gbps", "Tbps"]
    unit_index = 0

    while bps >= 1000 and unit_index < len(units) - 1:
        bps /= 1000
        unit_index += 1

    return f"{bps:.2f} {units[unit_index]}"


def speed_test_client_to_server():
    received_bytes = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, PORT))
        sock.listen(1)

        conn, _ = sock.accept()
        print("Client connected!")

        start_time = time.time()
        with conn:
            while True:
                data = conn.recv(BUFFER_SIZE)
                if not data:
                    break
                received_bytes += len(data)

        end_time = time.time()
        duration = end_time - start_time
        speed = format_speed(received_bytes, duration)

        sock.close()

        print("--- Download Test Results (Client -> Server) ---")
        print(f"Received {received_bytes / (1024*1024):.2f} MB in {duration:.2f} seconds")
        print(f"Download speed: {speed}")


def speed_test_server_to_client():
    FILE_SIZE = 10 * 1024 * 1024  # 10MB
    data = b"x" * FILE_SIZE       # Generate 10MB of data

    sent_bytes = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((HOST, PORT))
        sock.listen(1)

        conn, _ = sock.accept()
        print("Client connected!")

        start_time = time.time()
        while sent_bytes < FILE_SIZE:
            chunk = data[sent_bytes:sent_bytes+BUFFER_SIZE]
            conn.sendall(chunk)
            sent_bytes += len(chunk)
        end_time = time.time()
        duration = end_time - start_time
        speed = format_speed(sent_bytes, duration)

        sock.close()

        print("--- Upload Test Results (Server -> Client) ---")
        print(f"Sent {sent_bytes / (1024*1024):.2f} MB in {duration:.2f} seconds")
        print(f"Download speed: {speed}")


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
    max_timeout = 10  # Stop listening after 10 seconds

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((HOST, PORT))
        sock.settimeout(5)

        requested_timeout = 0
        try:
            while requested_timeout < max_timeout:
                data, addr = sock.recvfrom(BUFFER_SIZE)

                # Extract requested timeout (client sends as struct "d" - double)
                requested_timeout = struct.unpack("d", data)[0]
                print(f"Received timeout request: {requested_timeout:.2f}")

                # Wait and send response
                time.sleep(requested_timeout)
                sock.sendto(b"", addr)
        except socket.timeout:
            print("No new request received from client.")

        print(f"Minimum hole lifetime: {requested_timeout}")


if __name__ == "__main__":
    print("# Server waiting on upload...")
    speed_test_client_to_server()

    print("\n# Server waiting to download...")
    speed_test_server_to_client()

    print("\n# UDP echo server listening...")
    udp_latency_server()

    print("\n# UDP hole lifetime server listening...")
    udp_hole_duration()
