package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker

/**
 * Latency message for RTT measurement.
 * Viewer sends this message and streamer echoes it back.
 * RTT/2 gives an approximation of one-way latency.
 */
class Latency(
    timestamp: Double = System.currentTimeMillis() / 1000.0
) : Message(timestamp) {

    override val type: String = "Latency"

    companion object {
        fun fromPayload(payload: Map<String, Any>, timestamp: Double) =
            Latency(timestamp = timestamp)
    }

    override fun packPayload(packer: MessageBufferPacker) {
        packer.packMapHeader(0)
    }

    override fun toString(): String {
        return "Latency(timestamp=$timestamp)"
    }
}
