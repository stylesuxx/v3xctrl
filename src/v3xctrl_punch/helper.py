import logging
import socket
import threading
import time

from rpi_4g_streamer.Message import Heartbeat


def control_loop(sock: socket, remote_addr):
    sock_name = sock.getsockname()
    sock_formatted = f"{sock_name[0]}:{sock_name[1]}"
    remote_addr_formatted = f"{remote_addr[0]}:{remote_addr[1]}"

    def receiver():
        logging.info(f"[C] Listening on {sock_formatted}")
        while True:
            _, addr = sock.recvfrom(1024)
            logging.info(f"[C] from {addr[0]}:{addr[1]}")

    def sender():
        logging.info(f"[C] Sending from {sock_formatted} to {remote_addr_formatted}")
        while True:
            sock.sendto(Heartbeat().to_bytes(), remote_addr)
            logging.info(f"[C] to   {remote_addr_formatted}")
            time.sleep(1)

    threading.Thread(target=receiver, daemon=True).start()
    threading.Thread(target=sender, daemon=True).start()


def bind_udp(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', port))

    return sock
