package com.v3xctrl.viewer.network.tcp

import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.Socket
import java.net.SocketException

private const val TAG = "TcpTunnel"

// Retry backoff sequence (milliseconds)
private val RETRY_DELAYS_MS = longArrayOf(1000, 2000, 5000)
private const val CONNECT_WARN_TIMEOUT_MS = 30_000L
private const val CONNECT_TIMEOUT_MS = 5000
private const val UDP_BUFFER_SIZE = 65535
private const val SELECT_TIMEOUT_MS = 1000

/**
 * TCP tunnel client that bridges local UDP to a remote TCP endpoint.
 *
 * UDP proxy model:
 * - Binds a UDP socket on localhost:0 (ephemeral port E)
 * - Outbound: local component sends to localhost:E -> proxy reads -> forwards over TCP
 * - Inbound: TCP data -> proxy sends from E to localhost:localComponentPort
 * - Auto-reconnects on TCP disconnect (UDP proxy stays bound)
 */
class TcpTunnel(
    private val remoteHost: String,
    private val remotePort: Int,
    private val localComponentPort: Int,
    private val bidirectional: Boolean = true,
    private val handshake: ByteArray? = null,
) {
    private var _ephemeralPort: Int = 0
    val ephemeralPort: Int get() = _ephemeralPort

    private var scope: CoroutineScope? = null
    private var mainJob: Job? = null
    private var udpSocket: DatagramSocket? = null

    @Volatile
    private var stopped = false

    fun start() {
        stopped = false
        val supervisorScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
        scope = supervisorScope

        mainJob = supervisorScope.launch {
            run()
        }
    }

    fun stop() {
        stopped = true
        try {
            udpSocket?.close()
        } catch (_: Exception) {}
        scope?.cancel()
        scope = null
        mainJob = null
    }

    private suspend fun run() {
        val udpSock = DatagramSocket(null).apply {
            reuseAddress = true
            bind(java.net.InetSocketAddress(InetAddress.getByName("127.0.0.1"), 0))
        }
        udpSocket = udpSock
        _ephemeralPort = udpSock.localPort

        Log.i(TAG, "UDP proxy bound on ephemeral port $_ephemeralPort")

        try {
            while (!stopped) {
                val tcpSock = connectWithRetry() ?: break

                if (handshake != null) {
                    if (!doHandshake(tcpSock)) {
                        tcpSock.close()
                        continue
                    }
                }

                Log.i(TAG, "Connected to $remoteHost:$remotePort")
                bridge(tcpSock, udpSock)
                tcpSock.close()

                if (!stopped) {
                    Log.w(TAG, "Disconnected from $remoteHost:$remotePort, reconnecting...")
                }
            }
        } finally {
            udpSock.close()
        }
    }

    private fun connectWithRetry(): Socket? {
        var attempt = 0
        val firstAttemptTime = System.currentTimeMillis()
        var warned = false

        while (!stopped) {
            val tcpSock = Socket()
            try {
                tcpSock.connect(
                    java.net.InetSocketAddress(remoteHost, remotePort),
                    CONNECT_TIMEOUT_MS
                )
                tcpSock.tcpNoDelay = true
                return tcpSock
            } catch (e: Exception) {
                tcpSock.close()
                val elapsed = System.currentTimeMillis() - firstAttemptTime

                if (!warned && elapsed >= CONNECT_WARN_TIMEOUT_MS) {
                    Log.e(
                        TAG,
                        "Cannot establish TCP connection to $remoteHost:$remotePort " +
                            "after ${elapsed / 1000}s - is the remote side configured for TCP?"
                    )
                    warned = true
                }

                val delayIdx = attempt.coerceAtMost(RETRY_DELAYS_MS.size - 1)
                val delayMs = RETRY_DELAYS_MS[delayIdx]
                Log.d(TAG, "TCP connect failed (${e.message}), retrying in ${delayMs}ms...")

                // Sleep in small increments to check stop flag
                val deadline = System.currentTimeMillis() + delayMs
                while (System.currentTimeMillis() < deadline) {
                    if (stopped) {
                        return null
                    }
                    Thread.sleep(100)
                }
                attempt++
            }
        }
        return null
    }

    private fun doHandshake(tcpSock: Socket): Boolean {
        val output = tcpSock.getOutputStream()
        val input = tcpSock.getInputStream()

        if (!TcpFraming.sendMessage(output, handshake!!)) {
            Log.e(TAG, "Handshake send failed")
            return false
        }

        val response = TcpFraming.recvMessage(input)
        if (response == null) {
            Log.e(TAG, "Handshake response failed (disconnected)")
            return false
        }

        Log.i(TAG, "Handshake complete (${response.size} bytes)")
        return true
    }

    private fun bridge(tcpSock: Socket, udpSock: DatagramSocket) {
        val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
        var inboundJob: Job? = null

        if (bidirectional) {
            inboundJob = scope.launch {
                inboundLoop(tcpSock, udpSock)
            }
        }

        try {
            // Outbound: UDP on ephemeral port -> TCP
            val buf = ByteArray(UDP_BUFFER_SIZE)
            val packet = DatagramPacket(buf, buf.size)
            udpSock.soTimeout = SELECT_TIMEOUT_MS

            while (!stopped) {
                try {
                    udpSock.receive(packet)
                } catch (_: java.net.SocketTimeoutException) {
                    // Check if TCP is still alive (for bidirectional, inbound handles this;
                    // for unidirectional, peek the TCP socket)
                    if (!bidirectional) {
                        try {
                            tcpSock.getInputStream()
                            if (tcpSock.isClosed || !tcpSock.isConnected) break
                        } catch (_: Exception) {
                            break
                        }
                    }
                    // Check if inbound thread died (bidirectional)
                    if (bidirectional && inboundJob?.isActive == false) break
                    continue
                } catch (_: SocketException) {
                    break
                }

                val data = packet.data.copyOf(packet.length)
                if (!TcpFraming.sendMessage(tcpSock.getOutputStream(), data)) {
                    break
                }
            }
        } catch (_: Exception) {
            // Bridge broken
        } finally {
            try {
                tcpSock.close()
            } catch (_: Exception) {}
            inboundJob?.cancel()
            scope.cancel()
        }
    }

    private fun inboundLoop(tcpSock: Socket, udpSock: DatagramSocket) {
        val localhost = InetAddress.getByName("127.0.0.1")
        try {
            val input = tcpSock.getInputStream()
            while (!stopped) {
                val data = TcpFraming.recvMessage(input) ?: break
                val packet = DatagramPacket(data, data.size, localhost, localComponentPort)
                udpSock.send(packet)
            }
        } catch (_: Exception) {
            // Inbound broken
        }
    }
}
