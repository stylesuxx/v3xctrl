"""
Transmit UDP packets that are being added to the queue.

Uses asyncio under the hood for the actual sending. There is no sanity checking
happening, as long as a valid UDP packet is added to the queue, it will be sent.

Since asyncio is used, its not enough to just run this Class, but instead you
also need to trigger starting of the task:

tx = UPDTransmitter()
tx.start()
tx.start_task()
...
tx.stop()
tx.join()
"""
import logging
import asyncio
from queue import Queue, Empty
import socket
import threading
from typing import Tuple

from .UDPPacket import UDPPacket
from .Message import Message


class UDPTransmitter(threading.Thread):
    def __init__(self):
        super().__init__()

        self.queue = Queue()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)

        self.loop = asyncio.new_event_loop()
        self.task = None

        self.running = threading.Event()
        self.process_stopped = threading.Event()

    def get_socket(self) -> socket.socket:
        """ In case the socket for sending should be re-used for listening. """
        return self.sock

    def add_message(self, message: Message, addr: Tuple[str, int]):
        """ Convenience function to add a message to the queue."""
        packet = UDPPacket(message.to_bytes(), addr[0], addr[1])
        self.add(packet)

    def add(self, udp_packet: UDPPacket) -> None:
        self.queue.put(udp_packet)

    def run(self) -> None:
        self.running.set()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def process(self):
        while self.running.is_set():
            try:
                packet = self.queue.get(timeout=1)
                address = (packet.host, packet.port)
                # await self.loop.sock_sendto(self.sock, packet.data, address)
                self.sock.sendto(packet.data, address)
                self.queue.task_done()
                print(f"Sent to: {address}")
            except Empty:
                pass
            except OSError as e:
                logging.warning(f"Socket error while sending: {e}")
            except Exception as e:
                logging.error(f"Unexpected transmit error: {e}", exc_info=True)

        self.process_stopped.set()

    def start_task(self):
        if not self.task:
            self.task = asyncio.run_coroutine_threadsafe(self.process(), self.loop)

    def stop(self) -> None:
        if self.running.is_set():
            self.running.clear()

            self.process_stopped.wait()

            self.task.cancel()
            self.loop.call_soon_threadsafe(self.loop.stop)

        self.sock.close()
