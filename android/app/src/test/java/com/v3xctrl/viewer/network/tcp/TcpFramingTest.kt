package com.v3xctrl.viewer.network.tcp

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

class TcpFramingTest {

  @Test
  fun sendAndReceiveRoundTrip() {
    val payload = "hello world".toByteArray()
    val outputStream = ByteArrayOutputStream()

    assertTrue(TcpFraming.sendMessage(outputStream, payload))

    val inputStream = ByteArrayInputStream(outputStream.toByteArray())
    val received = TcpFraming.recvMessage(inputStream)

    assertNotNull(received)
    assertArrayEquals(payload, received)
  }

  @Test
  fun emptyPayload() {
    val outputStream = ByteArrayOutputStream()

    assertTrue(TcpFraming.sendMessage(outputStream, byteArrayOf()))

    val inputStream = ByteArrayInputStream(outputStream.toByteArray())
    val received = TcpFraming.recvMessage(inputStream)

    assertNotNull(received)
    assertEquals(0, received!!.size)
  }

  @Test
  fun oversizedPayloadReturnsFalse() {
    val oversized = ByteArray(65536) // max is 65535
    val outputStream = ByteArrayOutputStream()

    assertFalse(TcpFraming.sendMessage(outputStream, oversized))
    assertEquals(0, outputStream.size())
  }

  @Test
  fun maxSizePayloadSucceeds() {
    val maxPayload = ByteArray(65535)
    val outputStream = ByteArrayOutputStream()

    assertTrue(TcpFraming.sendMessage(outputStream, maxPayload))

    val inputStream = ByteArrayInputStream(outputStream.toByteArray())
    val received = TcpFraming.recvMessage(inputStream)

    assertNotNull(received)
    assertEquals(65535, received!!.size)
  }

  @Test
  fun multipleMessagesInSequence() {
    val messages = listOf(
      "first".toByteArray(),
      "second".toByteArray(),
      "third".toByteArray()
    )

    val outputStream = ByteArrayOutputStream()
    for (message in messages) {
      assertTrue(TcpFraming.sendMessage(outputStream, message))
    }

    val inputStream = ByteArrayInputStream(outputStream.toByteArray())
    for (expected in messages) {
      val received = TcpFraming.recvMessage(inputStream)
      assertNotNull(received)
      assertArrayEquals(expected, received)
    }
  }

  @Test
  fun recvReturnsNullOnEmptyStream() {
    val inputStream = ByteArrayInputStream(byteArrayOf())
    assertNull(TcpFraming.recvMessage(inputStream))
  }

  @Test
  fun recvReturnsNullOnTruncatedHeader() {
    // Only 1 byte when header needs 2
    val inputStream = ByteArrayInputStream(byteArrayOf(0x00))
    assertNull(TcpFraming.recvMessage(inputStream))
  }
}
