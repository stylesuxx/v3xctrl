package com.v3xctrl.viewer.control

import android.util.Log
import com.v3xctrl.viewer.messages.Ack
import com.v3xctrl.viewer.messages.Command
import com.v3xctrl.viewer.messages.CommandAck
import com.v3xctrl.viewer.messages.Control
import com.v3xctrl.viewer.messages.Heartbeat
import com.v3xctrl.viewer.messages.Latency
import com.v3xctrl.viewer.messages.Message
import com.v3xctrl.viewer.messages.PeerAnnouncement
import com.v3xctrl.viewer.messages.PeerInfo
import com.v3xctrl.viewer.messages.PortType
import com.v3xctrl.viewer.messages.Role
import com.v3xctrl.viewer.messages.Syn
import com.v3xctrl.viewer.messages.Telemetry
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketException
import java.net.SocketTimeoutException
import java.util.concurrent.ConcurrentHashMap

private const val TAG = "UDPReceiver"
private const val BUFFER_SIZE = 65535
private const val SOCKET_TIMEOUT_MS = 1000
private const val ANNOUNCEMENT_INTERVAL_MS = 1000L
private const val DEFAULT_CONTROL_HZ = 30
private const val COMMAND_RETRY_DELAY_MS = 200L
private const val COMMAND_MAX_RETRIES = 10
private const val LATENCY_CHECK_INTERVAL_MS = 1000L

/**
 * Receives UDP packets on the control channel and processes messages.
 * Uses UDPTransmitter for sending messages.
 * Sends Control messages at the configured frequency when connected.
 */
class UDPReceiver(
    private val port: Int,
    private val relayHost: String,
    private val relayPort: Int,
    private val sessionId: String,
    private val scope: CoroutineScope,
    controlHz: Int = DEFAULT_CONTROL_HZ,
    private val controlState: ControlState? = null,
    private val viewerState: ViewerState? = null,
    private val spectatorMode: Boolean = false,
    private val forwardScale: Float = 1f,
    private val backwardScale: Float = 1f,
    private val steeringScale: Float = 1f
) {
    private val controlIntervalMs = (1000L / controlHz.coerceIn(1, 100))
    private val supervisorJob = SupervisorJob(scope.coroutineContext[Job])
    private val receiverScope = CoroutineScope(scope.coroutineContext + supervisorJob + Dispatchers.IO)
    private var socket: DatagramSocket? = null
    private var transmitter: UDPTransmitter? = null
    private var relayAddress: InetAddress? = null
    private var lastValidTimestamp: Double = 0.0
    private val pendingCommands = ConcurrentHashMap<String, (Boolean) -> Unit>()

    // Track the last address we received messages from (for sending responses)
    @Volatile private var lastPeerAddress: InetAddress? = null
    @Volatile private var lastPeerPort: Int = 0
    @Volatile private var isRunning = false
    @Volatile private var isConnected = false
    @Volatile private var receivedPeerInfo = false

    fun start() {
        if (isRunning) {
            return
        }

        isRunning = true

        // Launch initialization in IO dispatcher to avoid NetworkOnMainThreadException
        receiverScope.launch {
            try {
                relayAddress = InetAddress.getByName(relayHost)
                socket = DatagramSocket(port).apply {
                    soTimeout = SOCKET_TIMEOUT_MS
                }

                // Create and start transmitter
                transmitter = UDPTransmitter(socket!!, receiverScope).also { it.start() }

                Log.i(TAG, "Started UDPReceiver on port $port, relay: $relayHost:$relayPort, relayAddress: ${relayAddress?.hostAddress}")

                // Launch sub-jobs (all parented by supervisorJob)
                receiverScope.launch { receiveLoop() }
                receiverScope.launch { announcementLoop() }
                receiverScope.launch { stateLoop() }
                receiverScope.launch { latencyLoop() }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to start UDPReceiver: ${e.message}", e)
                isRunning = false
                cleanup()
            }
        }
    }

    private suspend fun announcementLoop() {
        while (isRunning && receiverScope.isActive && !receivedPeerInfo) {
            relayAddress?.let { addr ->
                val role = if (spectatorMode) Role.SPECTATOR else Role.VIEWER
                val announcement = PeerAnnouncement(
                    role = role,
                    sessionId = sessionId,
                    portType = PortType.CONTROL
                )
                send(announcement, addr, relayPort)
            }

            delay(ANNOUNCEMENT_INTERVAL_MS)
        }
    }

    private suspend fun stateLoop() {
        // Skip control loop when in spectator mode
        if (spectatorMode) {
            return
        }

        while (isRunning && receiverScope.isActive) {
            if (isConnected) {
                lastPeerAddress?.let { addr ->
                    val paused = controlState?.paused ?: false
                    if (paused) {
                        send(Control(throttle = 0.0, steering = 0.0), addr, lastPeerPort)
                    } else {
                        val rawThrottle = controlState?.throttle?.toDouble() ?: 0.0
                        val throttle = if (rawThrottle >= 0) rawThrottle * forwardScale else rawThrottle * backwardScale
                        val steering = (controlState?.steering?.toDouble() ?: 0.0) * steeringScale
                        send(Control(throttle = throttle, steering = steering), addr, lastPeerPort)
                    }
                }
            }

            delay(controlIntervalMs)
        }
    }

    private suspend fun latencyLoop() {
        while (isRunning && receiverScope.isActive) {
            if (isConnected) {
                lastPeerAddress?.let { addr ->
                    send(Latency(), addr, lastPeerPort)
                }
            }

            delay(LATENCY_CHECK_INTERVAL_MS)
        }
    }

    fun stop() {
        isRunning = false
        supervisorJob.cancel()
        transmitter?.stop()
        transmitter = null

        // Fail all pending commands
        pendingCommands.forEach { (_, callback) ->
            callback(false)
        }
        pendingCommands.clear()

        cleanup()
    }

    private fun cleanup() {
        try {
            socket?.close()
        } catch (_: Exception) {
            // Ignore cleanup errors
        }
        socket = null
        relayAddress = null
        lastPeerAddress = null
        lastPeerPort = 0
        isConnected = false
        receivedPeerInfo = false
        lastValidTimestamp = 0.0
        viewerState?.isControlConnected = false
    }

    private fun receiveLoop() {
        val buffer = ByteArray(BUFFER_SIZE)
        val packet = DatagramPacket(buffer, buffer.size)

        while (isRunning && receiverScope.isActive) {
            try {
                socket?.receive(packet) ?: break

                val data = packet.data.copyOf(packet.length)
                processPacket(data, packet.address, packet.port)
            } catch (_: SocketTimeoutException) {
                // Expected timeout, continue loop
                continue
            } catch (e: SocketException) {
                if (isRunning) {
                    Log.e(TAG, "Socket error: ${e.message}")
                }
                break
            } catch (e: Exception) {
                Log.e(TAG, "Error receiving packet: ${e.message}", e)
            }
        }
    }

    private fun processPacket(data: ByteArray, address: InetAddress, port: Int) {
        val host = address.hostAddress ?: "unknown"
        val messageType = Message.peekType(data)
        val message = try {
            Message.fromBytes(data)
        } catch (e: Exception) {
            Log.w(TAG, "Failed to parse message from $host:$port: ${e.message}")
            return
        }

        if (message == null) {
            Log.d(TAG, "Unknown message type '$messageType' from $host:$port")
            return
        }

        // Validate timestamp ordering (skip out-of-order messages)
        // Latency, Command, and CommandAck are order-agnostic
        val isOrderAgnostic = message is Latency || message is Command || message is CommandAck
        if (!isOrderAgnostic && message.timestamp < lastValidTimestamp) {
            Log.d(TAG, "Skipping out-of-order ${message.type} message")
            return
        }

        if (!isOrderAgnostic) {
            lastValidTimestamp = message.timestamp
        }

        viewerState?.onControlMessageReceived()
        handleMessage(message, address, port)
    }

    private fun handleMessage(message: Message, address: InetAddress, port: Int) {
        when (message) {
            is PeerInfo -> handlePeerInfo(message)
            is Syn -> handleSyn(message, address, port)
            is Heartbeat -> { /* Silently handle keepalive */ }
            is Telemetry -> handleTelemetry(message)
            is CommandAck -> handleCommandAck(message)
            is Latency -> handleLatency(message)
            else -> Log.d(TAG, "Received ${message.type} message")
        }
    }

    private fun handlePeerInfo(peerInfo: PeerInfo) {
        Log.i(TAG, "Received PeerInfo: ${peerInfo.ip}:${peerInfo.videoPort}/${peerInfo.controlPort}")
        receivedPeerInfo = true
    }

    private fun handleSyn(syn: Syn, address: InetAddress, port: Int) {
        // Store the peer address for sending responses (like heartbeat)
        lastPeerAddress = address
        lastPeerPort = port

        Log.d(TAG, "Received Syn v${syn.version}, sending Ack to ${address.hostAddress}:$port")
        send(Ack(), address, port)

        if (!isConnected) {
            isConnected = true
            viewerState?.isControlConnected = true
            Log.i(TAG, "Connected to ${address.hostAddress}:$port")
        }
    }

    private fun handleCommandAck(ack: CommandAck) {
        val commandId = ack.commandId
        Log.d(TAG, "Received CommandAck for $commandId")

        val callback = pendingCommands.remove(commandId)
        if (callback != null) {
            callback(true)
        }
    }

    private fun handleTelemetry(telemetry: Telemetry) {
        Log.d(TAG, "Telemetry: ${formatTelemetryValues(telemetry.values)}")
        viewerState?.updateFromTelemetry(telemetry.values)
    }

    private fun handleLatency(latency: Latency) {
        viewerState?.updateLatency(latency.timestamp)
    }

    private fun send(message: Message, address: InetAddress, port: Int) {
        transmitter?.addMessage(message, address, port)
    }

    /**
     * Send a command with retry mechanism.
     * The callback is called with true if acknowledged, false if timed out.
     */
    fun sendCommand(command: Command, callback: (Boolean) -> Unit) {
        if (!isConnected || lastPeerAddress == null) {
            Log.w(TAG, "Cannot send command: not connected")
            callback(false)

            return
        }

        val commandId = command.commandId
        pendingCommands[commandId] = callback

        // Launch retry coroutine
        receiverScope.launch {
            for (attempt in 0 until COMMAND_MAX_RETRIES) {
                // Check if already acknowledged
                if (!pendingCommands.containsKey(commandId)) {
                    return@launch
                }

                Log.d(TAG, "Sending command ${command.command} (attempt ${attempt + 1}/$COMMAND_MAX_RETRIES)")
                lastPeerAddress?.let { addr ->
                    send(command, addr, lastPeerPort)
                }

                // Wait before next retry (except after last attempt)
                if (attempt < COMMAND_MAX_RETRIES - 1) {
                    delay(COMMAND_RETRY_DELAY_MS)
                }
            }

            // Timeout - no ACK received
            val cb = pendingCommands.remove(commandId)
            if (cb != null) {
                Log.w(TAG, "Command $commandId timed out after $COMMAND_MAX_RETRIES attempts")
                cb(false)
            }
        }
    }

    private fun formatTelemetryValues(values: Map<String, Any>): String {
        return values.entries.joinToString(", ") { (key, value) ->
            when (value) {
                is Map<*, *> -> "$key={${formatNestedMap(value)}}"
                else -> "$key=$value"
            }
        }
    }

    @Suppress("UNCHECKED_CAST")
    private fun formatNestedMap(map: Map<*, *>): String {
        return map.entries.joinToString(", ") { (key, value) ->
            when (value) {
                is Map<*, *> -> "$key={${formatNestedMap(value)}}"
                else -> "$key=$value"
            }
        }
    }
}
