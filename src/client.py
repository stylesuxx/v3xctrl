import argparse

from rpi_4g_streamer import Client


parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("host", help="The target IP address")
parser.add_argument("port", type=int, help="The target port number")
args = parser.parse_args()

HOST = args.host
PORT = args.port

client = Client(HOST, PORT)
client.start()
client.join()
