package com.v3xctrl.viewer

import com.v3xctrl.viewer.control.VideoPortKeepAlive
import com.v3xctrl.viewer.messages.Heartbeat
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.msgpack.core.MessagePack
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

class VideoPortKeepAliveTest {

    private lateinit var relaySocket: DatagramSocket
    private var relayPort: Int = 0

    @Before
    fun setUp() {
        // Simulate a relay by listening on a random port
        relaySocket = DatagramSocket(0)
        relaySocket.soTimeout = 2000
        relayPort = relaySocket.localPort
    }

    @After
    fun tearDown() {
        relaySocket.close()
    }

    @Test
    fun intervalIsShortWhenVideoNotRunning() {
        val keepAlive = VideoPortKeepAlive(
            videoPort = 0,
            relayAddress = InetAddress.getLoopbackAddress(),
            relayPort = relayPort
        )
        assertEquals(
            VideoPortKeepAlive.INTERVAL_IDLE_MS,
            keepAlive.getIntervalMs(isVideoRunning = false)
        )
    }

    @Test
    fun intervalIsLongWhenVideoIsRunning() {
        val keepAlive = VideoPortKeepAlive(
            videoPort = 0,
            relayAddress = InetAddress.getLoopbackAddress(),
            relayPort = relayPort
        )
        assertEquals(
            VideoPortKeepAlive.INTERVAL_STREAMING_MS,
            keepAlive.getIntervalMs(isVideoRunning = true)
        )
    }

    @Test
    fun heartbeatIsValidMsgpack() {
        val bytes = Heartbeat().toBytes()
        assertTrue("Serialized bytes should not be empty", bytes.isNotEmpty())

        // Verify the msgpack structure: {t: "Heartbeat", p: {}, d: <timestamp>}
        val unpacker = MessagePack.newDefaultUnpacker(bytes)
        val mapSize = unpacker.unpackMapHeader()
        assertEquals("Top-level map should have 3 entries", 3, mapSize)

        val fields = mutableMapOf<String, Any>()
        repeat(mapSize) {
            val key = unpacker.unpackString()
            when (key) {
                "t" -> fields[key] = unpacker.unpackString()
                "d" -> fields[key] = unpacker.unpackDouble()
                "p" -> {
                    val payloadSize = unpacker.unpackMapHeader()
                    fields[key] = payloadSize
                }
            }
        }

        assertEquals("Heartbeat", fields["t"])
        assertEquals(0, fields["p"])
        assertTrue("Timestamp should be positive", (fields["d"] as Double) > 0)
    }

    @Test
    fun heartbeatArrivesAtRelay() {
        val keepAlive = VideoPortKeepAlive(
            videoPort = 0,
            relayAddress = InetAddress.getLoopbackAddress(),
            relayPort = relayPort
        )

        val socket = DatagramSocket()
        try {
            keepAlive.sendHeartbeat(socket)

            val buffer = ByteArray(1024)
            val packet = DatagramPacket(buffer, buffer.size)
            relaySocket.receive(packet)

            assertTrue("Packet should contain data", packet.length > 0)

            // Verify the received data is a Heartbeat message
            val unpacker = MessagePack.newDefaultUnpacker(
                packet.data, 0, packet.length
            )
            val mapSize = unpacker.unpackMapHeader()
            assertEquals(3, mapSize)

            var messageType: String? = null
            repeat(mapSize) {
                val key = unpacker.unpackString()
                if (key == "t") {
                    messageType = unpacker.unpackString()
                } else {
                    unpacker.skipValue()
                }
            }
            assertEquals("Heartbeat", messageType)
        } finally {
            socket.close()
        }
    }
}
