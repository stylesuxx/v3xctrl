import atlib
import socket
import time
import argparse
import csv
from datetime import datetime

CSV_FILE = "udp_speed_log.csv"


def rsrp_to_dbm(value: int) -> int:
    if value == 255:
        return -140  # Unknown
    return value - 140


def rsrq_to_dbm(value: int) -> float:
    if value == 255:
        return -20.0  # Unknown
    return (value * 0.5) - 19.5


def tcp_upload(ip: str, port: int) -> float:
    BUFFER_SIZE = 4096
    FILE_SIZE = 10 * 1024 * 1024  # 10MB
    data = b"x" * FILE_SIZE

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip, port))
        sent_bytes = 0

        start_time = time.time()
        while sent_bytes < FILE_SIZE:
            chunk = data[sent_bytes: sent_bytes + BUFFER_SIZE]
            sock.sendall(chunk)
            sent_bytes += len(chunk)

        elapsed = time.time() - start_time

        mbps = (sent_bytes * 8) / (1_000_000 * elapsed)
        return mbps


def log_to_csv(timestamp: str, mbps: float, rsrp_dbm: int, rsrq_dbm: int):
    """Appends test result to a CSV file."""
    write_header = not CSV_FILE or not os.path.exists(CSV_FILE)
    with open(CSV_FILE, mode="a", newline="") as file:
        writer = csv.writer(file)
        if write_header:
            writer.writerow(["timestamp", "mbps", "rsrp_dbm", "rsrq_dbm"])
        writer.writerow([timestamp, f"{mbps:.2f}", rsrp_dbm, rsrq_dbm])


def monitor_and_test(server_ip: str, port: int, modem: str):
    print("Monitoring signal quality...")
    gsm = atlib.AIR780EU(modem)
    last_rsrp_dbm = None
    try:
        while True:
            rsrq, rsrp = gsm.get_signal_quality()
            rsrq_dbm = rsrq_to_dbm(rsrq)
            rsrp_dbm = rsrp_to_dbm(rsrp)

            if rsrp_dbm != last_rsrp_dbm:
                timestamp = datetime.now().isoformat()
                mbps = tcp_upload(server_ip, port)
                log_to_csv(timestamp, mbps, rsrp_dbm, rsrq_dbm)
                print(f"[{timestamp}] RSRQ: {rsrq_dbm}, RSRP: {rsrp_dbm} Speed: {mbps:.2f} Mbps")
                last_rsrp_dbm = rsrp_dbm
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    import os
    parser = argparse.ArgumentParser(description="Monitor signal and send UDP packets to iperf3 server on change.")
    parser.add_argument("ip", help="IP address of the iperf3 server")
    parser.add_argument("port", type=int, help="UDP port of the iperf3 server")
    parser.add_argument("modem", type=int, help="Modem path")

    args = parser.parse_args()
    monitor_and_test(args.ip, args.port, args.modem)
