package com.v3xctrl.viewer.messages

import org.msgpack.core.MessageBufferPacker
import org.msgpack.core.MessagePack
import org.msgpack.core.MessageUnpacker
import org.msgpack.value.ValueType

/**
 * Abstract base class for all messages with built-in serialization.
 * Short keys are used to save space when packing messages.
 */
abstract class Message(
    val timestamp: Double = System.currentTimeMillis() / 1000.0
) {
    /**
     * The message type name, derived from the class name.
     */
    open val type: String
        get() = this::class.simpleName ?: "Unknown"

    /**
     * Pack the payload fields into the MessageBufferPacker.
     * Subclasses must implement this to pack their specific fields.
     */
    protected abstract fun packPayload(packer: MessageBufferPacker)

    @Suppress("UNCHECKED_CAST")
    protected fun packMap(packer: MessageBufferPacker, map: Map<String, Any>) {
        packer.packMapHeader(map.size)
        for ((key, value) in map) {
            packer.packString(key)
            packValue(packer, value)
        }
    }

    private fun packValue(packer: MessageBufferPacker, value: Any) {
        when (value) {
            is String -> packer.packString(value)
            is Int -> packer.packInt(value)
            is Long -> packer.packLong(value)
            is Double -> packer.packDouble(value)
            is Float -> packer.packFloat(value)
            is Boolean -> packer.packBoolean(value)
            is Map<*, *> -> packMap(packer, value as Map<String, Any>)
            else -> packer.packString(value.toString())
        }
    }

    /**
     * Serialize the message to bytes using msgpack.
     * Format: {"t": type, "p": payload, "d": timestamp}
     */
    fun toBytes(): ByteArray {
        val packer = MessagePack.newDefaultBufferPacker()
        packer.packMapHeader(3)

        // type
        packer.packString("t")
        packer.packString(type)

        // payload
        packer.packString("p")
        packPayload(packer)

        // timestamp (seconds since epoch as float, matching Python's time.time())
        packer.packString("d")
        packer.packDouble(timestamp)

        packer.close()
        return packer.toByteArray()
    }

    companion object {
        private val registry: Map<String, (Map<String, Any>, Double) -> Message> = mapOf(
            "Ack" to Ack::fromPayload,
            "Command" to Command::fromPayload,
            "CommandAck" to CommandAck::fromPayload,
            "Control" to Control::fromPayload,
            "Error" to Error::fromPayload,
            "Heartbeat" to Heartbeat::fromPayload,
            "Latency" to Latency::fromPayload,
            "PeerAnnouncement" to PeerAnnouncement::fromPayload,
            "PeerInfo" to PeerInfo::fromPayload,
            "Syn" to Syn::fromPayload,
            "Telemetry" to Telemetry::fromPayload,
        )

        /**
         * Deserialize bytes into the correct message subclass.
         */
        fun fromBytes(data: ByteArray): Message? {
            return try {
                val unpacker = MessagePack.newDefaultUnpacker(data)
                val mapSize = unpacker.unpackMapHeader()

                var messageType: String? = null
                var payload: Map<String, Any>? = null
                var timestamp = 0.0

                repeat(mapSize) {
                    val key = unpacker.unpackString()
                    when (key) {
                        "t" -> messageType = unpacker.unpackString()
                        "d" -> timestamp = unpacker.unpackDouble()
                        "p" -> payload = unpackMap(unpacker)
                    }
                }
                unpacker.close()

                val type = messageType ?: return null
                val factory = registry[type] ?: return null
                factory(payload ?: emptyMap(), timestamp)
            } catch (_: Exception) {
                null
            }
        }

        /**
         * Peek at the message type without full deserialization.
         */
        fun peekType(data: ByteArray): String {
            return try {
                val unpacker = MessagePack.newDefaultUnpacker(data)
                val mapSize = unpacker.unpackMapHeader()

                repeat(mapSize) {
                    val key = unpacker.unpackString()
                    if (key == "t") {
                        return unpacker.unpackString()
                    } else {
                        unpacker.skipValue()
                    }
                }
                unpacker.close()
                "Unknown"
            } catch (_: Exception) {
                "Unknown"
            }
        }

        private fun unpackMap(unpacker: MessageUnpacker): Map<String, Any> {
            val mapSize = unpacker.unpackMapHeader()
            val result = mutableMapOf<String, Any>()

            repeat(mapSize) {
                val key = unpacker.unpackString()
                result[key] = unpackValue(unpacker)
            }

            return result
        }

        private fun unpackValue(unpacker: MessageUnpacker): Any {
            val format = unpacker.nextFormat
            return when (format.valueType) {
                ValueType.STRING -> unpacker.unpackString()
                ValueType.INTEGER -> unpacker.unpackLong()
                ValueType.BOOLEAN -> unpacker.unpackBoolean()
                ValueType.FLOAT -> unpacker.unpackDouble()
                ValueType.MAP -> unpackMap(unpacker)
                ValueType.ARRAY -> unpackArray(unpacker)
                ValueType.NIL -> {
                    unpacker.unpackNil()
                    "null"
                }
                else -> unpacker.unpackValue().toString()
            }
        }

        private fun unpackArray(unpacker: MessageUnpacker): List<Any> {
            val arraySize = unpacker.unpackArrayHeader()
            val result = mutableListOf<Any>()
            repeat(arraySize) {
                result.add(unpackValue(unpacker))
            }

            return result
        }
    }
}
