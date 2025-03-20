import argparse
import socket
import struct
import time
import os


parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("host", help="The target IP address")
parser.add_argument("port", type=int, help="The target port number")
args = parser.parse_args()

SERVER_IP = args.host
PORT = args.port


def upload_test():
    BUFFER_SIZE = 4096
    FILE_SIZE = 10 * 1024 * 1024  # 10MB
    data = os.urandom(FILE_SIZE)  # Generate 10MB of random data

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        sent_bytes = 0

        client_socket.connect((SERVER_IP, PORT))

        while sent_bytes < FILE_SIZE:
            chunk = data[sent_bytes:sent_bytes+BUFFER_SIZE]
            client_socket.sendall(chunk)
            sent_bytes += len(chunk)


def udp_rtt_test():
    BUFFER_SIZE = 1024
    NUM_PACKETS = 100
    latencies = []

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        client_socket.settimeout(1)  # Timeout for response

        for i in range(NUM_PACKETS):
            try:
                start_time = time.time()  # Record send time

                client_socket.sendto(b"", (SERVER_IP, PORT))  # Send packet
                data, _ = client_socket.recvfrom(BUFFER_SIZE)  # Wait for reply

                end_time = time.time()
                rtt_ms = (end_time - start_time) * 1000

                latencies.append(rtt_ms)

            except socket.timeout:
                print(f"Packet {i+1}/{NUM_PACKETS}: Timed out")
                latencies.append(None)

        valid_latencies = [lat for lat in latencies if lat is not None]
        if valid_latencies:
            mean_rtt = sum(valid_latencies) / len(valid_latencies)
            min_rtt = min(valid_latencies)
            max_rtt = max(valid_latencies)

            results = "--- UDP RTT Test Results ---\n"
            results += f"Sent: {NUM_PACKETS}, Received: {len(valid_latencies)}, Lost: {NUM_PACKETS - len(valid_latencies)}\n"
            results += f"Mean RTT: {mean_rtt:.2f} ms, Best RTT: {min_rtt:.2f} ms, Worst RTT: {max_rtt:.2f} ms\n"
            results += f"Estimated One-Way Latency (RTT/2): {mean_rtt/2:.2f} ms"

            client_socket.sendto(results.encode("utf-8"), (SERVER_IP, PORT))
        else:
            print("\nAll packets were lost. Check your network!")


def udp_hole_test():
    BUFFER_SIZE = 1024
    TIMEOUT_INCREMENT = 1  # Timeout in seconds to detect NAT closure
    MAX_TIMEOUT = 30       # Stop after 30seconds if still open
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        timeout_value = TIMEOUT_INCREMENT

        while timeout_value <= MAX_TIMEOUT:
            client_socket.sendto(struct.pack("d", timeout_value), (SERVER_IP, PORT))
            client_socket.settimeout(timeout_value + 5)

            try:
                client_socket.recvfrom(BUFFER_SIZE)
                timeout_value += TIMEOUT_INCREMENT

            except socket.timeout:
                break


if __name__ == "__main__":
    print(f"Connecting to {SERVER_IP}:{PORT}")

    print("Starting speed test...")
    upload_test()

    print("Starting UDP RTT test...")
    udp_rtt_test()

    print("Starting UDP hole duration test...")
    time.sleep(5)
    udp_hole_test()
