import socket
import time

from rpi_4g_streamer import MessageHandler, UDPTransmitter
from rpi_4g_streamer.Message import Heartbeat

HOST = "0.0.0.0"
PORT = 6666

sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_tx.settimeout(1)

sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_rx.bind((HOST, PORT))
sock_rx.settimeout(1)


def hh_handler(message, addr):
    print(f"Received heartbeat from {addr}: {message}")


handler = MessageHandler(sock_rx)
handler.start()

handler.add_handler(Heartbeat, hh_handler)

transmitter = UDPTransmitter(sock_tx)
transmitter.start()
transmitter.start_task()

transmitter.add_message(Heartbeat(), (HOST, PORT))

# Allow some time to finish processing
time.sleep(1)

transmitter.stop()
transmitter.join()

handler.stop()
handler.join()

sock_rx.close()
sock_tx.close()
