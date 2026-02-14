package com.v3xctrl.viewer.relay

import android.util.Log
import com.v3xctrl.viewer.messages.Message
import com.v3xctrl.viewer.messages.PeerAnnouncement
import com.v3xctrl.viewer.messages.PeerInfo
import com.v3xctrl.viewer.messages.PortType
import com.v3xctrl.viewer.messages.Role
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

private const val TAG = "RelayConnection"

sealed class ConnectionResult {
    data class Success(
        val peerInfo: PeerInfo,
        val videoPort: Int,
        val controlPort: Int
    ) : ConnectionResult()
    data class Unauthorized(val message: String) : ConnectionResult()
    data class Error(val message: String) : ConnectionResult()
    data object Cancelled : ConnectionResult()
}

private sealed class AnnouncementResult {
    data class Received(val peerInfo: PeerInfo) : AnnouncementResult()
    data object Unauthorized : AnnouncementResult()
    data object Pending : AnnouncementResult()
}

class RelayConnection(
    private val relayHost: String,
    private val relayPort: Int,
    private val sessionId: String,
    private val spectatorMode: Boolean = false
) {
    companion object {
        private const val MAX_HANDSHAKE_ATTEMPTS = 60
        private const val ANNOUNCEMENT_INTERVAL_MS = 500L
        private const val SOCKET_TIMEOUT_MS = 5000
        private const val RECEIVE_BUFFER_SIZE = 1024
    }

    private var videoSocket: DatagramSocket? = null
    private var controlSocket: DatagramSocket? = null

    // Actual ports assigned by the system
    private var actualVideoPort: Int = 0
    private var actualControlPort: Int = 0

    @Volatile private var cancelled = false

    suspend fun connect(timeoutMs: Long = 30000): ConnectionResult = withContext(Dispatchers.IO) {
        try {
            withTimeout(timeoutMs) {
                performHandshake()
            }
        } catch (_: kotlinx.coroutines.TimeoutCancellationException) {
            cleanup()
            ConnectionResult.Error("Connection timeout")
        } catch (e: Exception) {
            cleanup()
            if (cancelled) {
                ConnectionResult.Cancelled
            } else {
                ConnectionResult.Error(e.message ?: "Unknown error")
            }
        }
    }

    private suspend fun performHandshake(): ConnectionResult = withContext(Dispatchers.IO) {
        Log.d(TAG, "Starting handshake with relay $relayHost:$relayPort for session $sessionId")

        val relayAddress = try {
            InetAddress.getByName(relayHost)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to resolve relay host: $relayHost", e)
            return@withContext ConnectionResult.Error("Failed to resolve host: ${e.message}")
        }

        // Create sockets with dynamic port assignment
        try {
            // 0 = let system assign a port
            videoSocket = DatagramSocket(0)
            controlSocket = DatagramSocket(0)

            actualVideoPort = videoSocket!!.localPort
            actualControlPort = controlSocket!!.localPort
            Log.d(TAG, "Created sockets on ports $actualVideoPort (video) and $actualControlPort (control)")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create sockets", e)
            return@withContext ConnectionResult.Error("Failed to create sockets: ${e.message}")
        }

        videoSocket?.soTimeout = SOCKET_TIMEOUT_MS
        controlSocket?.soTimeout = SOCKET_TIMEOUT_MS

        // Send announcements for both ports
        val role = if (spectatorMode) Role.SPECTATOR else Role.VIEWER
        val videoAnnouncement = PeerAnnouncement(
            role = role,
            sessionId = sessionId,
            portType = PortType.VIDEO
        )
        val controlAnnouncement = PeerAnnouncement(
            role = role,
            sessionId = sessionId,
            portType = PortType.CONTROL
        )

        var videoPeerInfo: PeerInfo? = null
        var controlPeerInfo: PeerInfo? = null

        // Keep sending announcements until we get responses for both
        var attempts = 0

        while (!cancelled && (videoPeerInfo == null || controlPeerInfo == null) && attempts < MAX_HANDSHAKE_ATTEMPTS) {
            attempts++

            if (videoPeerInfo == null) {
                when (val result = announceAndReceive(videoSocket!!, videoAnnouncement, relayAddress, relayPort)) {
                    is AnnouncementResult.Received -> videoPeerInfo = result.peerInfo
                    is AnnouncementResult.Unauthorized -> {
                        cleanup()
                        return@withContext ConnectionResult.Unauthorized("Session ID not authorized")
                    }
                    is AnnouncementResult.Pending -> {}
                }
            }

            if (controlPeerInfo == null) {
                when (val result = announceAndReceive(controlSocket!!, controlAnnouncement, relayAddress, relayPort)) {
                    is AnnouncementResult.Received -> controlPeerInfo = result.peerInfo
                    is AnnouncementResult.Unauthorized -> {
                        cleanup()
                        return@withContext ConnectionResult.Unauthorized("Session ID not authorized")
                    }
                    is AnnouncementResult.Pending -> {}
                }
            }

            // Wait before next attempt
            if (videoPeerInfo == null || controlPeerInfo == null) {
                delay(ANNOUNCEMENT_INTERVAL_MS)
            }
        }

        if (cancelled) {
            cleanup()
            return@withContext ConnectionResult.Cancelled
        }

        if (videoPeerInfo != null && controlPeerInfo != null) {
            // Store ports before cleanup
            val videoPort = actualVideoPort
            val controlPort = actualControlPort

            // Close sockets so GStreamer and UDPReceiver can bind to the same ports
            cleanup()
            ConnectionResult.Success(videoPeerInfo, videoPort, controlPort)
        } else {
            cleanup()
            ConnectionResult.Error("Failed to establish connection")
        }
    }

    private fun announceAndReceive(
        socket: DatagramSocket,
        announcement: PeerAnnouncement,
        address: InetAddress,
        port: Int
    ): AnnouncementResult {
        sendAnnouncement(socket, announcement, address, port)
        return when (val response = receiveResponse(socket)) {
            is PeerInfo -> AnnouncementResult.Received(response)
            is com.v3xctrl.viewer.messages.Error ->
                if (response.isUnauthorized) AnnouncementResult.Unauthorized
                else AnnouncementResult.Pending
            else -> AnnouncementResult.Pending
        }
    }

    private fun sendAnnouncement(
        socket: DatagramSocket,
        announcement: PeerAnnouncement,
        address: InetAddress,
        port: Int
    ) {
        val data = announcement.toBytes()
        val packet = DatagramPacket(data, data.size, address, port)
        try {
            socket.send(packet)
            Log.d(TAG, "Sent ${announcement.portType} announcement to ${address.hostAddress}:$port (${data.size} bytes)")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send announcement", e)
        }
    }

    private fun receiveResponse(socket: DatagramSocket): Message? {
        return try {
            val buffer = ByteArray(RECEIVE_BUFFER_SIZE)
            val packet = DatagramPacket(buffer, buffer.size)
            socket.receive(packet)
            Log.d(TAG, "Received ${packet.length} bytes from ${packet.address.hostAddress}:${packet.port}")
            val msg = Message.fromBytes(packet.data.copyOf(packet.length))
            Log.d(TAG, "Parsed message: ${msg?.type ?: "null"}")
            msg
        } catch (_: java.net.SocketTimeoutException) {
            // Expected timeout, no logging needed
            null
        } catch (e: Exception) {
            Log.e(TAG, "Error receiving response", e)
            null
        }
    }

    fun cancel() {
        cancelled = true
        cleanup()
    }

    private fun cleanup() {
        try {
            videoSocket?.close()
            controlSocket?.close()
        } catch (_: Exception) {
            // Ignore cleanup errors
        }
        videoSocket = null
        controlSocket = null
    }
}
