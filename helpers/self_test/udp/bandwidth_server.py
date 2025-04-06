import socket
import time
import argparse
import traceback

BUFFER_SIZE = 4096


def format_speed(bytes_received: int, duration: float) -> str:
    if duration <= 0:
        return "N/A"
    mbps = (bytes_received * 8) / (1000000 * duration)
    return f"{mbps:.2f} Mbps"


def run_tcp_upload_server(port: int):
    print(f"Starting TCP upload server on port {port}...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', port))
            sock.listen(1)

            while True:
                try:
                    print("Waiting for client...")
                    conn, addr = sock.accept()
                    print(f"+ Client connected from {addr}")

                    received_bytes = 0
                    start_time = time.time()

                    with conn:
                        while True:
                            try:
                                data = conn.recv(BUFFER_SIZE)
                                if not data:
                                    break
                                received_bytes += len(data)
                            except (ConnectionResetError, BrokenPipeError) as e:
                                print(f"Connection error: {e}")
                                break

                        try:
                            conn.sendall(b'DONE')
                        except Exception as e:
                            print(f"Failed to send DONE ack: {e}")

                    duration = time.time() - start_time
                    speed = format_speed(received_bytes, duration)

                    print("--- Transfer Complete ---")
                    print(f"Received {received_bytes / (1024*1024):.2f} MB in {duration:.2f} seconds")
                    print(f"Upload speed: {speed}\n")

                except Exception as e:
                    print(f"Error during client handling: {e}")
                    traceback.print_exc()

    except Exception as e:
        print(f"Fatal server error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TCP Upload Server with ACK")
    parser.add_argument("port", type=int, help="Port to listen on")

    args = parser.parse_args()
    run_tcp_upload_server(args.port)
