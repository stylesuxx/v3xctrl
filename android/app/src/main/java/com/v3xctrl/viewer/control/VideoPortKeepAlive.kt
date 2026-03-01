package com.v3xctrl.viewer.control

import com.v3xctrl.viewer.messages.Heartbeat
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress

/**
 * Sends periodic Heartbeat packets from the video port to the relay server
 * to keep the NAT mapping alive. Heartbeats are sent at a higher rate when
 * video is not yet running (to punch the NAT hole) and at a lower rate during
 * active streaming (to prevent the mapping from expiring).
 */
class VideoPortKeepAlive(
    private val videoPort: Int,
    private val relayAddress: InetAddress,
    private val relayPort: Int
) {
    companion object {
        /** Keepalive interval when video is not running (NAT hole punch). */
        const val INTERVAL_IDLE_MS = 1_000L

        /** Keepalive interval during active streaming (NAT mapping refresh). */
        const val INTERVAL_STREAMING_MS = 30_000L
    }

    fun getIntervalMs(isVideoRunning: Boolean): Long =
        if (isVideoRunning) INTERVAL_STREAMING_MS else INTERVAL_IDLE_MS

    fun createSocket(): DatagramSocket = DatagramSocket(null).apply {
        reuseAddress = true
        bind(InetSocketAddress(videoPort))
    }

    fun sendHeartbeat(socket: DatagramSocket) {
        val data = Heartbeat().toBytes()
        val packet = DatagramPacket(data, data.size, relayAddress, relayPort)
        socket.send(packet)
    }
}
