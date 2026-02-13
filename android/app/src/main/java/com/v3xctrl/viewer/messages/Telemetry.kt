package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker

class Telemetry(
    val values: Map<String, Any> = emptyMap(),
    timestamp: Double = System.currentTimeMillis() / 1000.0
) : Message(timestamp) {

    override val type: String = "Telemetry"

    companion object {
        @Suppress("UNCHECKED_CAST")
        fun fromPayload(payload: Map<String, Any>, timestamp: Double) = Telemetry(
            values = payload["v"] as? Map<String, Any> ?: emptyMap(),
            timestamp = timestamp
        )
    }

    override fun packPayload(packer: MessageBufferPacker) {
        packer.packMapHeader(1)
        packer.packString("v")
        packMap(packer, values)
    }

    override fun toString(): String {
        return "Telemetry(values=$values, timestamp=$timestamp)"
    }
}
