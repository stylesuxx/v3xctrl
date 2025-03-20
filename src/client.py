from rpi_4g_streamer import Client

HOST = '127.0.0.1'
PORT = 6666

client = Client(HOST, PORT)
client.start()
client.join()
