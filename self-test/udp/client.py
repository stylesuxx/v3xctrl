import argparse
import socket
import time
import datetime
import math

parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("host", help="The target IP address")
parser.add_argument("port", type=int, help="The target port number")
parser.add_argument("--interval", type=int, default=10, help="Logging interval in minutes (default: 10)")
args = parser.parse_args()

HOST = args.host
PORT = args.port
REPORT_INTERVAL = args.interval * 60

BUFFER_SIZE = 1024


def udp_rtt_test() -> None:
    buffer_window = []

    send_time = time.time()
    min_runtime = 24 * 60 * 60
    target = send_time + min_runtime
    end_time = math.ceil(target / 3600) * 3600

    print("timestamp\tcount\tloss\tmean\tmin\tmax")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        client_socket.settimeout(1)

        # Align to the next clock-aligned boundary
        now = time.time()
        next_report_time = math.ceil(now / REPORT_INTERVAL) * REPORT_INTERVAL

        packet_counter = 0
        while time.time() < end_time:
            try:
                data_send = bytes([packet_counter % 10])
                send_time = time.time()
                client_socket.sendto(data_send, (HOST, PORT))
                data, _ = client_socket.recvfrom(BUFFER_SIZE)
                recv_time = time.time()

                if data_send != data:
                    buffer_window.append((end_time, None))
                else:
                    rtt_ms = (recv_time - send_time) * 1000
                    buffer_window.append((recv_time, rtt_ms))

            except socket.timeout:
                now = time.time()
                buffer_window.append((now, None))

            packet_counter += 1

            now = time.time()
            if now >= next_report_time:
                print_combined_rtt_report(buffer_window, now)
                next_report_time += REPORT_INTERVAL
                buffer_window = []

            time.sleep(1)


def print_combined_rtt_report(buffer: bytes, now: int) -> None:
    timestamp = datetime.datetime.now().replace(microsecond=0).isoformat()

    buffer_all = [rtt for t, rtt in buffer if now - t <= REPORT_INTERVAL]
    buffer_valid = [rtt for rtt in buffer_all if rtt is not None]

    if buffer_valid:
        avg = sum(buffer_valid) / len(buffer_valid)
        min_rtt = min(buffer_valid)
        max_rtt = max(buffer_valid)
        loss = (1 - len(buffer_valid) / len(buffer_all)) * 100
        print(f"{timestamp}\t{len(buffer_all)}\t{loss:.1f}\t{avg:.2f}\t{min_rtt:.2f}\t{max_rtt:.2f}")
    else:
        print(f"{timestamp}\t0\t100.0\tNaN\tNaN\tNaN")


if __name__ == "__main__":
    udp_rtt_test()
