"""
Send UDP packets that are added to queue.

Uses asyncio under the hood for the actual sending
"""
import asyncio
from queue import Queue
import socket
import threading

from .UDPPacket import UDPPacket


class UDPSender(threading.Thread):
    def __init__(self):
        super().__init__()

        self.running = False
        self.queue = Queue()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)
        self.loop = asyncio.new_event_loop()
        self.task = None

    def add(self, udp_packet: UDPPacket) -> None:
        self.queue.put(udp_packet)

    def run(self) -> None:
        self.running = True
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def process(self):
        while self.running:
            if self.queue.qsize() > 0:
                packet = self.queue.get()
                address = (packet.host, packet.port)
                await self.loop.sock_sendto(self.sock, packet.data, address)

            await asyncio.sleep(0)

    def start_task(self):
        self.task = asyncio.run_coroutine_threadsafe(self.process(), self.loop)

    def stop(self) -> None:
        self.running = False
        self.loop.call_soon_threadsafe(self.loop.stop)
