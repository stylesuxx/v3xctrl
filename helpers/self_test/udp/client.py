import argparse
import socket
import time
import datetime
import math


parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("host", help="The target IP address")
parser.add_argument("port", type=int, help="The target port number")
args = parser.parse_args()

HOST = args.host
PORT = args.port

BUFFER_SIZE = 1024
NUM_PACKETS = 1000


def udp_rtt_test():
    BUFFER_WINDOW = []
    FIFTEEN_MIN = 15 * 60
    ONE_HOUR = 60 * 60
    END_TIME = time.time() + 24 * 60 * 60

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        client_socket.settimeout(1)

        packet_counter = 0

        # Align to the next clock-aligned 15-minute boundary
        now = time.time()
        next_report_time = math.ceil(now / FIFTEEN_MIN) * FIFTEEN_MIN

        while time.time() < END_TIME:
            try:
                start_time = time.time()
                client_socket.sendto(b"", (HOST, PORT))
                data, _ = client_socket.recvfrom(BUFFER_SIZE)
                end_time = time.time()

                rtt_ms = (end_time - start_time) * 1000
                BUFFER_WINDOW.append((end_time, rtt_ms))

            except socket.timeout:
                now = time.time()
                BUFFER_WINDOW.append((now, None))
                print(f"Packet {packet_counter + 1:5}/∞: Timed out")

            packet_counter += 1

            # Keep only one hour
            now = time.time()
            BUFFER_WINDOW = [(t, rtt) for t, rtt in BUFFER_WINDOW if now - t <= ONE_HOUR]

            if now >= next_report_time:
                print_combined_rtt_report(BUFFER_WINDOW, now)

                next_report_time = math.ceil(now / FIFTEEN_MIN) * FIFTEEN_MIN + FIFTEEN_MIN

            time.sleep(1)


def print_combined_rtt_report(buffer, now):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    buffer_15m = [rtt for t, rtt in buffer if now - t <= 15 * 60 and rtt is not None]
    buffer_1h = [rtt for t, rtt in buffer if rtt is not None]

    print(f"\n[{timestamp}] --- RTT Report (Rolling Averages) ---")

    if buffer_15m:
        avg_15 = sum(buffer_15m) / len(buffer_15m)
        min_15 = min(buffer_15m)
        max_15 = max(buffer_15m)
        print(f"Last 15 min - Samples: {len(buffer_15m):5} | "
              f"Mean RTT: {avg_15:.2f} ms | Min: {min_15:.2f} ms | Max: {max_15:.2f} ms")
    else:
        print("Last 15 min  - No valid packets.")

    if buffer_1h:
        avg_1h = sum(buffer_1h) / len(buffer_1h)
        min_1h = min(buffer_1h)
        max_1h = max(buffer_1h)
        print(f"Last hour   - Samples: {len(buffer_1h):5} | "
              f"Mean RTT: {avg_1h:.2f} ms | Min: {min_1h:.2f} ms | Max: {max_1h:.2f} ms")
    else:
        print("Last  hour   - No valid packets.")


if __name__ == "__main__":
    print(f"Connecting to {HOST}:{PORT}")
    udp_rtt_test()
