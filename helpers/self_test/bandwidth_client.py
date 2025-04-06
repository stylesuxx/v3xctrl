import argparse
import atlib
import socket
import time
import csv
import os
from datetime import datetime

CSV_FILE = "bandwidth_log.csv"
BUFFER_SIZE = 4096

MB = 5
FILE_SIZE = MB * 1024 * 1024
DATA = b"x" * FILE_SIZE


def rsrp_to_dbm(value: int) -> int:
    return -140 if value == 255 else value - 140


def rsrq_to_dbm(value: int) -> float:
    return -20.0 if value == 255 else (value * 0.5) - 19.5


def tcp_upload(ip: str, port: int) -> float | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(15.0)
            sock.connect((ip, port))
            sent_bytes = 0

            start_time = time.time()
            while sent_bytes < FILE_SIZE:
                chunk = DATA[sent_bytes: sent_bytes + BUFFER_SIZE]
                sock.sendall(chunk)
                sent_bytes += len(chunk)

            # Let the server know we are done
            sock.shutdown(socket.SHUT_WR)

            # Wait for server acknowledgment
            try:
                sock.settimeout(10.0)
                ack = b''
                while len(ack) < 4:
                    chunk = sock.recv(4 - len(ack))
                    if not chunk:
                        print("[TCP] Connection closed before full ACK.")
                        return None
                    ack += chunk
                if ack != b'DONE':
                    print(f"[TCP] Unexpected response from server: {ack}")
                    return None
            except socket.timeout:
                print("[TCP] Timeout waiting for DONE ACK from server.")
                return None

            elapsed = time.time() - start_time
            mbps = (sent_bytes * 8) / (1_000_000 * elapsed)
            return mbps
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"[TCP] Upload failed: {e}")
        return None


def log_to_csv(timestamp: str, mbps: float | None, rsrp_dbm: int, rsrq_dbm: float):
    try:
        write_header = not os.path.exists(CSV_FILE)
        with open(CSV_FILE, mode="a", newline="") as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(["timestamp", "mbps", "rsrp_dbm", "rsrq_dbm"])
            writer.writerow([timestamp, f"{mbps:.2f}" if mbps is not None else "N/A", rsrp_dbm, rsrq_dbm])
    except OSError as e:
        print(f"[LOG] Failed to write to CSV: {e}")


def monitor_and_test(server_ip: str, port: int, modem: str):
    print("Monitoring signal quality...")
    gsm = atlib.AIR780EU(modem)
    last_rsrp_dbm = None
    try:
        while True:
            try:
                rsrq, rsrp = gsm.get_signal_quality()
                rsrq_dbm = rsrq_to_dbm(rsrq)
                rsrp_dbm = rsrp_to_dbm(rsrp)
            except Exception as e:
                print(f"[MODEM] Failed to read signal quality: {e}")
                time.sleep(2)
                continue

            if rsrp_dbm != last_rsrp_dbm:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                mbps = tcp_upload(server_ip, port)
                log_to_csv(timestamp, mbps, rsrp_dbm, rsrq_dbm)
                print(f"[{timestamp}] RSRQ: {rsrq_dbm:.1f}, RSRP: {rsrp_dbm} dBm, Speed: {mbps:.2f} Mbps" if mbps else f"[{timestamp}] RSRQ: {rsrq_dbm:.1f}, RSRP: {rsrp_dbm} dBm, Upload failed.")
                last_rsrp_dbm = rsrp_dbm

            time.sleep(0.001)
    except KeyboardInterrupt:
        print("\nStopped by user.")


def main():
    parser = argparse.ArgumentParser(description="Monitor signal and send upload data to server on signal change.")
    parser.add_argument("ip", help="IP address of the upload server")
    parser.add_argument("port", type=int, help="TCP port of the upload server")
    parser.add_argument("modem", type=str, help="Modem device path (e.g., /dev/ttyUSB2)")

    args = parser.parse_args()
    monitor_and_test(args.ip, args.port, args.modem)


if __name__ == "__main__":
    main()
