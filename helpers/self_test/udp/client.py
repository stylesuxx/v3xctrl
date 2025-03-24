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

        # Align to the next clock-aligned 15-minute boundary
        now = time.time()
        next_report_time = math.ceil(now / FIFTEEN_MIN) * FIFTEEN_MIN
        print(f"Next report at {next_report_time}")

        packet_counter = 0
        while time.time() < END_TIME:
            try:
                data_send = b""
                start_time = time.time()
                client_socket.sendto(data_send, (HOST, PORT))
                data, _ = client_socket.recvfrom(BUFFER_SIZE)
                end_time = time.time()

                if data_send != data:
                    BUFFER_WINDOW.append((end_time, None))
                    print(f"Packet {packet_counter + 1:5}/∞: Data mismatch")
                else:
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

                next_report_time += FIFTEEN_MIN
                print(f"Next report at {next_report_time}")

            time.sleep(1)


def print_combined_rtt_report(buffer, now):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    buffer_15m_all = [rtt for t, rtt in buffer if now - t <= 15 * 60]
    buffer_15m_valid = [rtt for rtt in buffer_15m_all if rtt is not None]

    buffer_1h_all = [rtt for t, rtt in buffer if now - t <= 60 * 60]
    buffer_1h_valid = [rtt for rtt in buffer_1h_all if rtt is not None]

    print(f"\n[{timestamp}] --- RTT Report (Rolling Averages) ---")

    if buffer_15m_valid:
        avg_15 = sum(buffer_15m_valid) / len(buffer_15m_valid)
        min_15 = min(buffer_15m_valid)
        max_15 = max(buffer_15m_valid)
        loss_15 = (1 - len(buffer_15m_valid) / len(buffer_15m_all)) * 100
        print(f"Last 15 min - Packets: {len(buffer_15m_all):5} | "
              f"Loss: {loss_15:5.1f}% | "
              f"Mean RTT: {avg_15:.2f} ms | Min: {min_15:.2f} ms | Max: {max_15:.2f} ms")
    else:
        print("Last 15 min - No valid packets.")

    if buffer_1h_valid:
        avg_1h = sum(buffer_1h_valid) / len(buffer_1h_valid)
        min_1h = min(buffer_1h_valid)
        max_1h = max(buffer_1h_valid)
        loss_1h = (1 - len(buffer_1h_valid) / len(buffer_1h_all)) * 100
        print(f"Last hour   - Packets: {len(buffer_1h_all):5} | "
              f"Loss: {loss_1h:5.1f}% | "
              f"Mean RTT: {avg_1h:.2f} ms | Min: {min_1h:.2f} ms | Max: {max_1h:.2f} ms")
    else:
        print("Last hour   - No valid packets.")


if __name__ == "__main__":
    print(f"Connecting to {HOST}:{PORT}")
    udp_rtt_test()
