package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker

class Ack(
    timestamp: Double = System.currentTimeMillis() / 1000.0
) : Message(timestamp) {

    override val type: String = "Ack"

    companion object {
        fun fromPayload(payload: Map<String, Any>, timestamp: Double) =
            Ack(timestamp = timestamp)
    }

    override fun packPayload(packer: MessageBufferPacker) {
        packer.packMapHeader(0)
    }

    override fun toString(): String {
        return "Ack(timestamp=$timestamp)"
    }
}
