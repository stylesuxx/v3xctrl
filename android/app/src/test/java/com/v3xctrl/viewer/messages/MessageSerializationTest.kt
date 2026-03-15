package com.v3xctrl.viewer.messages

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.msgpack.core.MessagePack

class MessageSerializationTest {

  /**
   * Helper to unpack a message's bytes and return its fields as a map.
   * This tests serialization without depending on fromBytes().
   */
  private fun unpackMessage(bytes: ByteArray): Triple<String, Map<String, Any>, Double> {
    val unpacker = MessagePack.newDefaultUnpacker(bytes)
    val mapSize = unpacker.unpackMapHeader()
    assertEquals(3, mapSize)

    var type = ""
    var timestamp = 0.0
    val payload = mutableMapOf<String, Any>()

    repeat(mapSize) {
      val key = unpacker.unpackString()
      when (key) {
        "t" -> type = unpacker.unpackString()
        "d" -> timestamp = unpacker.unpackDouble()
        "p" -> {
          val payloadSize = unpacker.unpackMapHeader()
          repeat(payloadSize) {
            val pk = unpacker.unpackString()
            val pv = unpacker.unpackValue()
            payload[pk] = when {
              pv.isStringValue -> pv.asStringValue().asString()
              pv.isIntegerValue -> pv.asIntegerValue().toLong()
              pv.isFloatValue -> pv.asFloatValue().toDouble()
              pv.isBooleanValue -> pv.asBooleanValue().boolean
              pv.isMapValue -> {
                val m = mutableMapOf<String, Any>()
                for ((mk, mv) in pv.asMapValue().map()) {
                  m[mk.asStringValue().asString()] = when {
                    mv.isStringValue -> mv.asStringValue().asString()
                    mv.isIntegerValue -> mv.asIntegerValue().toLong()
                    mv.isFloatValue -> mv.asFloatValue().toDouble()
                    else -> mv.toString()
                  }
                }
                m
              }
              else -> pv.toString()
            }
          }
        }
      }
    }
    unpacker.close()
    return Triple(type, payload, timestamp)
  }

  @Test
  fun heartbeatSerialization() {
    val (type, payload, timestamp) = unpackMessage(Heartbeat(timestamp = 1000.5).toBytes())
    assertEquals("Heartbeat", type)
    assertTrue(payload.isEmpty())
    assertEquals(1000.5, timestamp, 0.001)
  }

  @Test
  fun ackSerialization() {
    val (type, payload, timestamp) = unpackMessage(Ack(timestamp = 2000.0).toBytes())
    assertEquals("Ack", type)
    assertTrue(payload.isEmpty())
    assertEquals(2000.0, timestamp, 0.001)
  }

  @Test
  fun latencySerialization() {
    val (type, payload, timestamp) = unpackMessage(Latency(timestamp = 3000.0).toBytes())
    assertEquals("Latency", type)
    assertTrue(payload.isEmpty())
    assertEquals(3000.0, timestamp, 0.001)
  }

  @Test
  fun synSerialization() {
    val (type, payload, timestamp) = unpackMessage(Syn(version = 2, timestamp = 4000.0).toBytes())
    assertEquals("Syn", type)
    assertEquals(2L, payload["v"])
    assertEquals(4000.0, timestamp, 0.001)
  }

  @Test
  fun errorSerialization() {
    val (type, payload, timestamp) = unpackMessage(
      Error(error = "something went wrong", timestamp = 5000.0).toBytes()
    )
    assertEquals("Error", type)
    assertEquals("something went wrong", payload["e"])
    assertEquals(5000.0, timestamp, 0.001)
  }

  @Test
  fun errorIsUnauthorized() {
    assertTrue(Error(error = "403").isUnauthorized)
    assertTrue(!Error(error = "500").isUnauthorized)
  }

  @Test
  @Suppress("UNCHECKED_CAST")
  fun controlSerialization() {
    val (type, payload, timestamp) = unpackMessage(
      Control(throttle = 0.75, steering = -0.5, timestamp = 6000.0).toBytes()
    )
    assertEquals("Control", type)
    val values = payload["v"] as Map<String, Any>
    assertEquals(0.75, values["throttle"] as Double, 0.001)
    assertEquals(-0.5, values["steering"] as Double, 0.001)
    assertEquals(6000.0, timestamp, 0.001)
  }

  @Test
  @Suppress("UNCHECKED_CAST")
  fun telemetrySerialization() {
    val values = mapOf<String, Any>("battery" to 85, "signal" to -70)
    val (type, payload, timestamp) = unpackMessage(
      Telemetry(values = values, timestamp = 7000.0).toBytes()
    )
    assertEquals("Telemetry", type)
    val decoded = payload["v"] as Map<String, Any>
    assertEquals(85L, decoded["battery"])
    assertEquals(-70L, decoded["signal"])
    assertEquals(7000.0, timestamp, 0.001)
  }

  @Test
  fun commandSerialization() {
    val (type, payload, timestamp) = unpackMessage(
      Command(
        command = "recording",
        parameters = mapOf("action" to "start"),
        commandId = "test-id-123",
        timestamp = 8000.0
      ).toBytes()
    )
    assertEquals("Command", type)
    assertEquals("recording", payload["c"])
    assertEquals("test-id-123", payload["i"])
    assertEquals(8000.0, timestamp, 0.001)
  }

  @Test
  fun commandAckSerialization() {
    val (type, payload, timestamp) = unpackMessage(
      CommandAck(commandId = "ack-id-456", timestamp = 9000.0).toBytes()
    )
    assertEquals("CommandAck", type)
    assertEquals("ack-id-456", payload["i"])
    assertEquals(9000.0, timestamp, 0.001)
  }

  @Test
  fun peerAnnouncementSerialization() {
    val (type, payload, timestamp) = unpackMessage(
      PeerAnnouncement(
        role = Role.VIEWER,
        sessionId = "session-789",
        portType = PortType.VIDEO,
        timestamp = 10000.0
      ).toBytes()
    )
    assertEquals("PeerAnnouncement", type)
    assertEquals("viewer", payload["r"])
    assertEquals("session-789", payload["i"])
    assertEquals("video", payload["p"])
    assertEquals(10000.0, timestamp, 0.001)
  }

  @Test
  fun peerInfoSerialization() {
    val (type, payload, timestamp) = unpackMessage(
      PeerInfo(
        ip = "192.168.1.100",
        videoPort = 5000,
        controlPort = 5001,
        timestamp = 11000.0
      ).toBytes()
    )
    assertEquals("PeerInfo", type)
    assertEquals("192.168.1.100", payload["ip"])
    assertEquals(5000L, payload["video_port"])
    assertEquals(5001L, payload["control_port"])
    assertEquals(11000.0, timestamp, 0.001)
  }

  @Test
  fun peekTypeReturnsCorrectType() {
    val messages = listOf(
      Heartbeat() to "Heartbeat",
      Ack() to "Ack",
      Control(throttle = 0.0, steering = 0.0) to "Control",
      Command(command = "test") to "Command",
      Error(error = "err") to "Error",
      Syn() to "Syn",
      Latency() to "Latency"
    )

    for ((message, expectedType) in messages) {
      assertEquals("peekType for $expectedType", expectedType, Message.peekType(message.toBytes()))
    }
  }

  @Test
  fun fromBytesReturnsNullOnGarbage() {
    assertNull(Message.fromBytes(byteArrayOf(0x00, 0x01, 0x02, 0xFF.toByte())))
  }

  @Test
  fun fromBytesReturnsNullOnEmptyArray() {
    assertNull(Message.fromBytes(byteArrayOf()))
  }

  @Test
  fun timestampIsPreserved() {
    val fixedTimestamp = 1710000000.123
    val (_, _, decoded) = unpackMessage(Heartbeat(timestamp = fixedTimestamp).toBytes())
    assertEquals(fixedTimestamp, decoded, 0.0001)
  }

  @Test
  fun commandsFactoryCreatesCorrectCommands() {
    val videoStart = Commands.videoStart()
    assertEquals("service", videoStart.command)
    assertEquals("start", videoStart.parameters["action"])
    assertEquals("v3xctrl-video", videoStart.parameters["name"])

    val recordingStop = Commands.recordingStop()
    assertEquals("recording", recordingStop.command)
    assertEquals("stop", recordingStop.parameters["action"])

    val shutdown = Commands.shutdown()
    assertEquals("shutdown", shutdown.command)
    assertTrue(shutdown.parameters.isEmpty())
  }
}
