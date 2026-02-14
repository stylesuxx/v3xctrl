package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker

class Syn(
    val version: Int = 1,
    timestamp: Double = System.currentTimeMillis() / 1000.0
) : Message(timestamp) {

    override val type: String = "Syn"

    companion object {
        fun fromPayload(payload: Map<String, Any>, timestamp: Double) = Syn(
            version = (payload["v"] as? Number)?.toInt() ?: 1,
            timestamp = timestamp
        )
    }

    override fun packPayload(packer: MessageBufferPacker) {
        packer.packMapHeader(1)
        packer.packString("v")
        packer.packInt(version)
    }

    override fun toString(): String {
        return "Syn(version=$version, timestamp=$timestamp)"
    }
}
