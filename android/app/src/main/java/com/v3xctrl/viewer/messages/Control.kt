package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker

/**
 * Control message for sending throttle and steering values.
 */
class Control(
    val values: Map<String, Any> = emptyMap(),
    timestamp: Double = System.currentTimeMillis() / 1000.0
) : Message(timestamp) {

    override val type: String = "Control"

    companion object {
        @Suppress("UNCHECKED_CAST")
        fun fromPayload(payload: Map<String, Any>, timestamp: Double) = Control(
            values = payload["v"] as? Map<String, Any> ?: emptyMap(),
            timestamp = timestamp
        )
    }

    constructor(
        throttle: Double,
        steering: Double,
        timestamp: Double = System.currentTimeMillis() / 1000.0
    ) : this(
        values = mapOf("throttle" to throttle, "steering" to steering),
        timestamp = timestamp
    )

    override fun packPayload(packer: MessageBufferPacker) {
        packer.packMapHeader(1)
        packer.packString("v")
        packMap(packer, values)
    }

    override fun toString(): String {
        return "Control(values=$values)"
    }
}
