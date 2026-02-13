package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker

class PeerInfo(
    val ip: String,
    val videoPort: Int,
    val controlPort: Int,
    timestamp: Double = System.currentTimeMillis() / 1000.0
) : Message(timestamp) {

    override val type: String = "PeerInfo"

    companion object {
        fun fromPayload(payload: Map<String, Any>, timestamp: Double) = PeerInfo(
            ip = payload["ip"] as? String ?: "",
            videoPort = (payload["video_port"] as? Number)?.toInt() ?: 0,
            controlPort = (payload["control_port"] as? Number)?.toInt() ?: 0,
            timestamp = timestamp
        )
    }

    override fun packPayload(packer: MessageBufferPacker) {
        packer.packMapHeader(3)
        packer.packString("ip")
        packer.packString(ip)

        packer.packString("video_port")
        packer.packInt(videoPort)

        packer.packString("control_port")
        packer.packInt(controlPort)
    }

    override fun toString(): String {
        return "PeerInfo(ip=$ip, videoPort=$videoPort, controlPort=$controlPort)"
    }
}
