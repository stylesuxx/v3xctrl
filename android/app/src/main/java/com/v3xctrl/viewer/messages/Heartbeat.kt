package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker

class Heartbeat(
    timestamp: Double = System.currentTimeMillis() / 1000.0
) : Message(timestamp) {

    override val type: String = "Heartbeat"

    companion object {
        fun fromPayload(payload: Map<String, Any>, timestamp: Double) =
            Heartbeat(timestamp = timestamp)
    }

    override fun packPayload(packer: MessageBufferPacker) {
        packer.packMapHeader(0)
    }

    override fun toString(): String {
        return "Heartbeat(timestamp=$timestamp)"
    }
}
