package com.v3xctrl.viewer.control

import android.util.Log
import com.v3xctrl.viewer.messages.Message
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

private const val TAG = "UDPTransmitter"
private const val DEFAULT_TTL_MS = 1000L

data class UDPPacket(
    val data: ByteArray,
    val address: InetAddress,
    val port: Int,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * Transmits UDP packets from a queue.
 * Drops packets that exceed TTL to prevent sending stale data.
 */
class UDPTransmitter(
    private val socket: DatagramSocket,
    private val scope: CoroutineScope,
    private val ttlMs: Long = DEFAULT_TTL_MS
) {
    private val packetChannel = Channel<UDPPacket>(Channel.UNLIMITED)
    private var transmitJob: Job? = null

    @Volatile private var isRunning = false
    @Volatile var lastSentTimestamp: Long = 0; private set

    fun start() {
        if (isRunning) {
            return
        }

        isRunning = true
        transmitJob = scope.launch(Dispatchers.IO) {
            processQueue()
        }
    }

    fun stop() {
        isRunning = false
        transmitJob?.cancel()
        transmitJob = null
        packetChannel.close()
    }

    fun addMessage(message: Message, address: InetAddress, port: Int) {
        val data = message.toBytes()
        val packet = UDPPacket(data, address, port)

        packetChannel.trySend(packet)
    }

    private suspend fun processQueue() {
        while (isRunning && scope.isActive) {
            val packet = packetChannel.receiveCatching().getOrNull() ?: break

            val age = System.currentTimeMillis() - packet.timestamp
            if (age > ttlMs) {
                Log.d(TAG, "Dropping old packet (age: ${age}ms)")
                continue
            }

            try {
                val datagramPacket = DatagramPacket(
                    packet.data,
                    packet.data.size,
                    packet.address,
                    packet.port
                )
                socket.send(datagramPacket)
                lastSentTimestamp = System.currentTimeMillis()
            } catch (e: Exception) {
                Log.w(TAG, "Socket error while sending: ${e.message}")
            }
        }
    }
}
