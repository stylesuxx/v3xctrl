package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker

class Error(
    val error: String,
    timestamp: Double = System.currentTimeMillis() / 1000.0
) : Message(timestamp) {

    override val type: String = "Error"

    companion object {
        fun fromPayload(payload: Map<String, Any>, timestamp: Double) = Error(
            error = payload["e"] as? String ?: "",
            timestamp = timestamp
        )
    }

    val isUnauthorized: Boolean
        get() = error == "403"

    override fun packPayload(packer: MessageBufferPacker) {
        packer.packMapHeader(1)
        packer.packString("e")
        packer.packString(error)
    }

    override fun toString(): String {
        return "Error(error=$error)"
    }
}
