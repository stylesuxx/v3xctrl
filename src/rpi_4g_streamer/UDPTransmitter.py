"""
Transmit UDP packets that are being added to the queue.

Uses asyncio under the hood for the actual sending. There is no sanity checking
happening, as long as a valid UDP packet is added to the queue, it will be sent.

Since asyncio is used, its not enough to just run this Class, but instead you
also need to trigger starting of the task:

tx = UDPTransmitter()
tx.start()
tx.start_task()
...
tx.stop()
tx.join()
"""
import asyncio
import logging
from queue import Queue, Empty
import socket
import threading
from typing import Tuple, Optional

from .UDPPacket import UDPPacket
from .Message import Message


class UDPTransmitter(threading.Thread):
    def __init__(self, sock: socket.socket):
        super().__init__()

        self.socket = sock

        self.queue = Queue()

        self.loop = asyncio.new_event_loop()
        self.task: Optional[asyncio.Future] = None

        self._running = threading.Event()
        self.process_stopped = threading.Event()

    def add_message(self, message: Message, addr: Tuple[str, int]):
        """ Convenience function to add a message to the queue."""
        packet = UDPPacket(message.to_bytes(), addr[0], addr[1])
        self.add(packet)

    def add(self, udp_packet: UDPPacket) -> None:
        self.queue.put(udp_packet)

    def run(self) -> None:
        self._running.set()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def process(self):
        try:
            while self._running.is_set():
                try:
                    packet = self.queue.get(timeout=1)
                    address = (packet.host, packet.port)
                    self.socket.sendto(packet.data, address)
                    self.queue.task_done()
                except Empty:
                    pass
                except OSError as e:
                    logging.warning(f"Socket error while sending: {e}")
                except Exception as e:
                    logging.error(f"Unexpected transmit error: {e}", exc_info=True)

        except asyncio.CancelledError:
            logging.info("Transmit task cancelled.")
        finally:
            self.process_stopped.set()

    def start_task(self):
        if not self.task:
            self.task = asyncio.run_coroutine_threadsafe(self.process(), self.loop)

    def is_running(self) -> bool:
        return self._running.is_set()

    def stop(self) -> None:
        """
        Stop the transmitter and join the thread.

        NOTE: `join()` is called internally to ensure the event loop
              is fully shut down before closing. This prevents segfaults
              caused by premature `loop.close()` while the thread is still
              alive.
        """
        if self._running.is_set():
            self._running.clear()

            self.process_stopped.wait()

            if self.task:
                self.loop.call_soon_threadsafe(self.task.cancel)
                self.task.result()
                self.task = None

            self.loop.call_soon_threadsafe(self.loop.stop)
            self.join()
            self.loop.close()
