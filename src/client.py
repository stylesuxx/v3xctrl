from rpi_4g_streamer import MessageHandler, UDPTransmitter, UDPPacket
from rpi_4g_streamer import Message, Heartbeat, Client

import time

HOST = '127.0.0.1'
PORT = 6666

client = Client(HOST, PORT)
client.start()
client.join()

"""
tx = UDPTransmitter()
tx.start()
tx.start_task()

heartbeat = Heartbeat()
packet = UDPPacket(heartbeat.to_bytes(), HOST, PORT)
tx.add(packet)

time.sleep(10)

client.stop()
tx.stop()

client.join()
tx.join()
"""