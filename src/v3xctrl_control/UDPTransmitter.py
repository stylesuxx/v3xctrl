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
import concurrent.futures
import logging
import socket
import threading
import time
from collections import deque
from queue import Empty, Queue

from v3xctrl_helper import Address

from .message import Message
from .UDPPacket import UDPPacket

logger = logging.getLogger(__name__)


class UDPTransmitter(threading.Thread):
    def __init__(self, sock: socket.socket, ttl_ms: int = 1000, control_buffer_capacity: int = 1) -> None:
        super().__init__(daemon=True)

        self.socket = sock

        self.queue: Queue[UDPPacket] = Queue()

        self._control_buffer: deque[UDPPacket] = deque(maxlen=control_buffer_capacity)
        self._control_lock = threading.Lock()
        self._last_control_drop_timestamp: float = 0

        self.loop = asyncio.new_event_loop()
        self.task: concurrent.futures.Future[None] | None = None

        self._running = threading.Event()
        self.process_stopped = threading.Event()

        self.ttl = ttl_ms / 1000

    def add_message(self, message: Message, addr: Address) -> None:
        """Convenience function to add a message to the regular queue."""
        packet = UDPPacket(message.to_bytes(), addr[0], addr[1])
        self.add(packet)

    def add(self, udp_packet: UDPPacket) -> None:
        self.queue.put(udp_packet)

    def set_control_message(self, message: Message, addr: Address) -> None:
        """Set a control message in the bounded buffer, evicting the oldest if full."""
        packet = UDPPacket(message.to_bytes(), addr[0], addr[1])
        with self._control_lock:
            if len(self._control_buffer) == self._control_buffer.maxlen:
                self._last_control_drop_timestamp = time.time()
                logger.debug("Evicting oldest control message from buffer")
            self._control_buffer.append(packet)

    def has_recent_control_drops(self, window: float = 1.0) -> bool:
        with self._control_lock:
            if self._last_control_drop_timestamp == 0:
                return False
            return time.time() - self._last_control_drop_timestamp < window

    def run(self) -> None:
        self._running.set()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def update_ttl(self, ttl_ms: int) -> None:
        self.ttl = ttl_ms / 1000

    def _send_packet(self, packet: UDPPacket) -> None:
        try:
            self.socket.sendto(packet.data, (packet.host, packet.port))
        except OSError as e:
            logger.warning(f"Socket error while sending: {e}")

    async def process(self) -> None:
        try:
            while self._running.is_set():
                sent_anything = False

                # Send the oldest control message from the buffer
                control_packet = None
                with self._control_lock:
                    if self._control_buffer:
                        control_packet = self._control_buffer.popleft()

                if control_packet:
                    self._send_packet(control_packet)
                    sent_anything = True

                # Also process one regular queue item (non-blocking)
                try:
                    packet = self.queue.get_nowait()

                    if time.time() - packet.timestamp > self.ttl:
                        message_type = Message.peek_type(packet.data)
                        logger.info(f"Not transmitting old packet of type: {message_type}")
                    else:
                        self._send_packet(packet)

                    self.queue.task_done()
                    sent_anything = True

                except Empty:
                    pass

                except Exception as e:
                    logger.error(f"Unexpected transmit error: {e}", exc_info=True)

                if not sent_anything:
                    await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            logger.info("Transmit task cancelled.")
        finally:
            self.process_stopped.set()

    def start_task(self) -> None:
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
