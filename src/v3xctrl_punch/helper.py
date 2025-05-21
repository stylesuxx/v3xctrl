import logging
import socket
import threading
import time

from rpi_4g_streamer.Message import Message, Heartbeat


def control_loop(sock: socket, remote_addr):
    def receiver():
        logging.info(f"[C] Listening on {sock.getsockname()}")
        while True:
            data, addr = sock.recvfrom(1024)
            msg = Message.from_bytes(data)
            logging.info(f"[C] from {addr[0]}:{addr[1]} - {msg}")

    def sender():
        logging.info(f"[C] Sending from {sock.getsockname()} to {remote_addr}")
        while True:
            sock.sendto(Heartbeat().to_bytes(), remote_addr)
            logging.info(f"[C] to {remote_addr}")
            time.sleep(1)

    threading.Thread(target=receiver, daemon=True).start()
    threading.Thread(target=sender, daemon=True).start()


def bind_udp(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', port))

    return sock
