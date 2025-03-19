from rpi_4g_streamer import Server


PORT = 6666

server = Server(PORT)
server.start()
server.join()
