package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker
import java.util.UUID

/**
 * Command message for sending commands to the streamer.
 * Includes a unique ID for acknowledgment tracking.
 */
class Command(
    val command: String,
    val parameters: Map<String, Any> = emptyMap(),
    val commandId: String = UUID.randomUUID().toString(),
    timestamp: Double = System.currentTimeMillis() / 1000.0
) : Message(timestamp) {

    override val type: String = "Command"

    companion object {
        @Suppress("UNCHECKED_CAST")
        fun fromPayload(payload: Map<String, Any>, timestamp: Double) = Command(
            command = payload["c"] as? String ?: "",
            parameters = payload["p"] as? Map<String, Any> ?: emptyMap(),
            commandId = payload["i"] as? String ?: "",
            timestamp = timestamp
        )
    }

    override fun packPayload(packer: MessageBufferPacker) {
        packer.packMapHeader(3)

        // command name
        packer.packString("c")
        packer.packString(command)

        // parameters map
        packer.packString("p")
        packMap(packer, parameters)

        // command ID
        packer.packString("i")
        packer.packString(commandId)
    }

    override fun toString(): String {
        return "Command(command=$command, parameters=$parameters, commandId=$commandId)"
    }
}
