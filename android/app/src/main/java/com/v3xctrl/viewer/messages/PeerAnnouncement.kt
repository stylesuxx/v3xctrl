package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker

enum class Role(val value: String) {
    VIEWER("viewer"),
    STREAMER("streamer"),
    SPECTATOR("spectator")
}

enum class PortType(val value: String) {
    VIDEO("video"),
    CONTROL("control")
}

class PeerAnnouncement(
    val role: String,
    val id: String,
    val portType: String,
    timestamp: Double = System.currentTimeMillis() / 1000.0
) : Message(timestamp) {

    override val type: String = "PeerAnnouncement"

    companion object {
        fun fromPayload(payload: Map<String, Any>, timestamp: Double) = PeerAnnouncement(
            role = payload["r"] as? String ?: "",
            id = payload["i"] as? String ?: "",
            portType = payload["p"] as? String ?: "",
            timestamp = timestamp
        )
    }

    constructor(
        role: Role,
        sessionId: String,
        portType: PortType,
        timestamp: Double = System.currentTimeMillis() / 1000.0
    ) : this(
        role = role.value,
        id = sessionId,
        portType = portType.value,
        timestamp = timestamp
    )

    override fun packPayload(packer: MessageBufferPacker) {
        packer.packMapHeader(3)
        packer.packString("r")
        packer.packString(role)

        packer.packString("i")
        packer.packString(id)

        packer.packString("p")
        packer.packString(portType)
    }

    override fun toString(): String {
        return "PeerAnnouncement(role=$role, id=$id, portType=$portType)"
    }
}
