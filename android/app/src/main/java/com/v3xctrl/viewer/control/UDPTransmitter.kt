package com.v3xctrl.viewer.control

import android.util.Log
import com.v3xctrl.viewer.messages.Message
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.selects.select
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.concurrent.atomic.AtomicLong

private const val TAG = "UDPTransmitter"
private const val DEFAULT_TTL_MS = 1000L
private const val DEFAULT_CONTROL_BUFFER_CAPACITY = 1

data class UDPPacket(
  val data: ByteArray,
  val address: InetAddress,
  val port: Int,
  val timestamp: Long = System.currentTimeMillis()
)

/**
 * Transmits UDP packets from a queue.
 * Drops packets that exceed TTL to prevent sending stale data.
 *
 * Control messages use a separate bounded channel so only the latest
 * control state is sent, preventing stale control inputs from queuing up.
 */
class UDPTransmitter(
  private val socket: DatagramSocket,
  private val scope: CoroutineScope,
  private val ttlMs: Long = DEFAULT_TTL_MS,
  private val controlBufferCapacity: Int = DEFAULT_CONTROL_BUFFER_CAPACITY
) {
  private val packetChannel = Channel<UDPPacket>(Channel.UNLIMITED)
  private val controlChannel = Channel<UDPPacket>(controlBufferCapacity)
  private var transmitJob: Job? = null

  private val lastControlDropTimestamp = AtomicLong(0)

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
    controlChannel.close()
  }

  fun addMessage(message: Message, address: InetAddress, port: Int) {
    val data = message.toBytes()
    val packet = UDPPacket(data, address, port)

    packetChannel.trySend(packet)
  }

  fun setControlMessage(message: Message, address: InetAddress, port: Int) {
    val data = message.toBytes()
    val packet = UDPPacket(data, address, port)

    // Drop oldest if full, keeping only the latest control state
    if (controlChannel.trySend(packet).isFailure) {
      controlChannel.tryReceive()
      lastControlDropTimestamp.set(System.currentTimeMillis())
      Log.d(TAG, "Evicting oldest control message from buffer")
      controlChannel.trySend(packet)
    }
  }

  fun hasRecentControlDrops(windowMs: Long = 1000L): Boolean {
    val last = lastControlDropTimestamp.get()
    if (last == 0L) {
      return false
    }
    return System.currentTimeMillis() - last < windowMs
  }

  private fun sendPacket(packet: UDPPacket) {
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

  private fun processPacket(packet: UDPPacket) {
    val age = System.currentTimeMillis() - packet.timestamp
    if (age <= ttlMs) {
      sendPacket(packet)
    } else {
      Log.d(TAG, "Dropping old packet (age: ${age}ms)")
    }
  }

  private suspend fun processQueue() {
    while (isRunning && scope.isActive) {
      // Suspend until either channel has data - no polling, no CPU waste
      select {
        controlChannel.onReceive { packet ->
          sendPacket(packet)
        }
        packetChannel.onReceive { packet ->
          processPacket(packet)
        }
      }

      // Drain any remaining ready packets without suspending
      while (true) {
        val control = controlChannel.tryReceive().getOrNull()
        if (control != null) {
          sendPacket(control)
        } else {
          break
        }
      }
      while (true) {
        val regular = packetChannel.tryReceive().getOrNull()
        if (regular != null) {
          processPacket(regular)
        } else {
          break
        }
      }
    }
  }
}
