import argparse

from rpi_4g_streamer import Server


parser = argparse.ArgumentParser(description="Test connection performance.")
parser.add_argument("port", type=int, help="The target port number")
args = parser.parse_args()

PORT = args.port

server = Server(PORT)
server.start()
server.join()
