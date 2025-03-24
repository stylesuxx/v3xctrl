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
    END_TIME = time.time() + 24 * 60 * 60

    print("timestamp\tcount\tloss\tmean\tmin\tmax")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        client_socket.settimeout(1)

        # Align to the next clock-aligned 15-minute boundary
        now = time.time()
        next_report_time = math.ceil(now / FIFTEEN_MIN) * FIFTEEN_MIN

        packet_counter = 0
        while time.time() < END_TIME:
            try:
                data_send = bytes([packet_counter % 10])
                start_time = time.time()
                client_socket.sendto(data_send, (HOST, PORT))
                data, _ = client_socket.recvfrom(BUFFER_SIZE)
                end_time = time.time()

                if data_send != data:
                    BUFFER_WINDOW.append((end_time, None))
                else:
                    rtt_ms = (end_time - start_time) * 1000
                    BUFFER_WINDOW.append((end_time, rtt_ms))

            except socket.timeout:
                now = time.time()
                BUFFER_WINDOW.append((now, None))

            packet_counter += 1

            # Keep only one hour
            now = time.time()
            BUFFER_WINDOW = [(t, rtt) for t, rtt in BUFFER_WINDOW if now - t <= FIFTEEN_MIN]

            if now >= next_report_time:
                print_combined_rtt_report(BUFFER_WINDOW, now)
                next_report_time += FIFTEEN_MIN

            time.sleep(1)


def print_combined_rtt_report(buffer, now):
    timestamp = datetime.datetime.now().isoformat()

    buffer_15m_valid = [rtt for rtt in buffer if rtt is not None]
    if buffer_15m_valid:
        avg_15 = sum(buffer_15m_valid) / len(buffer_15m_valid)
        min_15 = min(buffer_15m_valid)
        max_15 = max(buffer_15m_valid)
        loss_15 = (1 - len(buffer_15m_valid) / len(buffer)) * 100
        print(f"{timestamp}\t{len(buffer)}\t{loss_15:.1f}\t{avg_15:.2f}\t{min_15:.2f}\t{max_15:.2f}")
    else:
        print(f"{timestamp}\t0\t100.0\tNaN\tNaN\tNaN")


if __name__ == "__main__":
    udp_rtt_test()
