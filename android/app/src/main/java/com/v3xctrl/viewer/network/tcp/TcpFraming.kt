package com.v3xctrl.viewer.network.tcp

import java.io.InputStream
import java.io.OutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Length-prefixed TCP framing for UDP-over-TCP tunneling.
 *
 * Each message is framed as: [2-byte big-endian length][payload]
 * Max payload size is 65535 bytes.
 */
object TcpFraming {
    private const val HEADER_SIZE = 2
    private const val MAX_PAYLOAD_SIZE = 0xFFFF

    /**
     * Send a length-prefixed message. Returns false on error.
     */
    fun sendMessage(output: OutputStream, data: ByteArray): Boolean {
        if (data.size > MAX_PAYLOAD_SIZE) {
          return false
        }

        val header = ByteBuffer.allocate(HEADER_SIZE)
            .order(ByteOrder.BIG_ENDIAN)
            .putShort(data.size.toShort())
            .array()

        return try {
            output.write(header)
            output.write(data)
            output.flush()
            true
        } catch (_: Exception) {
            false
        }
    }

    /**
     * Read a length-prefixed message. Returns null on disconnect.
     */
    fun recvMessage(input: InputStream): ByteArray? {
        val header = recvExact(input, HEADER_SIZE) ?: return null
        val length = ByteBuffer.wrap(header)
            .order(ByteOrder.BIG_ENDIAN)
            .short.toInt() and 0xFFFF

        if (length == 0) {
          return ByteArray(0)
        }

        return recvExact(input, length)
    }

    /**
     * Read exactly n bytes from stream. Returns null on disconnect.
     */
    private fun recvExact(input: InputStream, n: Int): ByteArray? {
        val buf = ByteArray(n)
        var offset = 0
        while (offset < n) {
            val read = input.read(buf, offset, n - offset)
            if (read == -1) {
              return null
            }
            offset += read
        }
        return buf
    }
}
