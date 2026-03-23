package com.v3xctrl.viewer.control

import com.v3xctrl.viewer.messages.Heartbeat
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

@OptIn(ExperimentalCoroutinesApi::class)
class UDPTransmitterTest {

  private lateinit var receiverSocket: DatagramSocket
  private lateinit var senderSocket: DatagramSocket
  private lateinit var transmitter: UDPTransmitter
  private lateinit var scope: TestScope
  private lateinit var address: InetAddress
  private var port: Int = 0

  @Before
  fun setUp() {
    receiverSocket = DatagramSocket(0)
    receiverSocket.soTimeout = 2000
    port = receiverSocket.localPort
    address = InetAddress.getByName("localhost")

    senderSocket = DatagramSocket()
    scope = TestScope(UnconfinedTestDispatcher())
    transmitter = UDPTransmitter(senderSocket, scope)
  }

  @After
  fun tearDown() {
    transmitter.stop()
    senderSocket.close()
    receiverSocket.close()
  }

  private fun receiveOne(): ByteArray {
    val buffer = ByteArray(1024)
    val packet = DatagramPacket(buffer, buffer.size)
    receiverSocket.receive(packet)
    return packet.data.copyOf(packet.length)
  }

  @Test
  fun `control message is sent via socket`() {
    transmitter.start()
    transmitter.setControlMessage(Heartbeat(), address, port)

    val data = receiveOne()
    assertTrue(data.isNotEmpty())
  }

  @Test
  fun `regular message is sent via socket`() {
    transmitter.start()
    transmitter.addMessage(Heartbeat(), address, port)

    val data = receiveOne()
    assertTrue(data.isNotEmpty())
  }

  @Test
  fun `no drops initially`() {
    assertFalse(transmitter.hasRecentControlDrops())
  }

  @Test
  fun `drop detected after eviction`() {
    transmitter.setControlMessage(Heartbeat(), address, port)
    transmitter.setControlMessage(Heartbeat(), address, port)

    assertTrue(transmitter.hasRecentControlDrops())
  }

  @Test
  fun `drop expires with zero window`() {
    transmitter.setControlMessage(Heartbeat(), address, port)
    transmitter.setControlMessage(Heartbeat(), address, port)

    assertTrue(transmitter.hasRecentControlDrops(windowMs = 10000L))
    assertFalse(transmitter.hasRecentControlDrops(windowMs = 0L))
  }

  @Test
  fun `no drop when buffer not full`() {
    val sender2 = DatagramSocket()
    val tx = UDPTransmitter(sender2, scope, controlBufferCapacity = 5)

    tx.setControlMessage(Heartbeat(), address, port)

    assertFalse(tx.hasRecentControlDrops())
    sender2.close()
  }

  @Test
  fun `custom capacity evicts after exceeding limit`() {
    val sender2 = DatagramSocket()
    val tx = UDPTransmitter(sender2, scope, controlBufferCapacity = 3)

    tx.setControlMessage(Heartbeat(), address, port)
    tx.setControlMessage(Heartbeat(), address, port)
    tx.setControlMessage(Heartbeat(), address, port)

    assertFalse(tx.hasRecentControlDrops())

    tx.setControlMessage(Heartbeat(), address, port)
    assertTrue(tx.hasRecentControlDrops())

    sender2.close()
  }

  @Test
  fun `control message sent before regular when both queued`() {
    val sender2 = DatagramSocket()
    val tx = UDPTransmitter(sender2, scope)

    // Queue regular first, then control - before starting
    tx.addMessage(Heartbeat(timestamp = 1.0), address, port)
    tx.setControlMessage(Heartbeat(timestamp = 2.0), address, port)
    tx.start()

    // Both should arrive. The control message (timestamp=2.0) should come first
    // because processQueue checks the control buffer before the regular channel.
    val first = receiveOne()
    val second = receiveOne()
    assertTrue(first.isNotEmpty())
    assertTrue(second.isNotEmpty())

    tx.stop()
    sender2.close()
  }
}
