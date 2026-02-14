package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker

/**
 * CommandAck message - acknowledgment that a command was received.
 */
class CommandAck(
    val commandId: String,
    timestamp: Double = System.currentTimeMillis() / 1000.0
) : Message(timestamp) {

    override val type: String = "CommandAck"

    companion object {
        fun fromPayload(payload: Map<String, Any>, timestamp: Double) = CommandAck(
            commandId = payload["i"] as? String ?: "",
            timestamp = timestamp
        )
    }

    override fun packPayload(packer: MessageBufferPacker) {
        packer.packMapHeader(1)
        packer.packString("i")
        packer.packString(commandId)
    }

    override fun toString(): String {
        return "CommandAck(commandId=$commandId)"
    }
}
