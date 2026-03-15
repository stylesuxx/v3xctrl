package com.v3xctrl.viewer.messages

import org.junit.Assert.assertEquals
import org.junit.Test

class PeerAnnouncementTest {

  @Test
  fun roleEnumValuesMatchProtocol() {
    assertEquals("viewer", Role.VIEWER.value)
    assertEquals("streamer", Role.STREAMER.value)
    assertEquals("spectator", Role.SPECTATOR.value)
  }

  @Test
  fun portTypeEnumValuesMatchProtocol() {
    assertEquals("video", PortType.VIDEO.value)
    assertEquals("control", PortType.CONTROL.value)
  }

  @Test
  fun enumConstructorMatchesStringConstructor() {
    val fromEnum = PeerAnnouncement(
      role = Role.VIEWER,
      sessionId = "test-session",
      portType = PortType.CONTROL,
      timestamp = 1000.0
    )
    val fromString = PeerAnnouncement(
      role = "viewer",
      id = "test-session",
      portType = "control",
      timestamp = 1000.0
    )

    assertEquals(fromString.role, fromEnum.role)
    assertEquals(fromString.id, fromEnum.id)
    assertEquals(fromString.portType, fromEnum.portType)

    // Both should serialize identically
    val enumBytes = fromEnum.toBytes()
    val stringBytes = fromString.toBytes()

    val decodedEnum = Message.fromBytes(enumBytes) as PeerAnnouncement
    val decodedString = Message.fromBytes(stringBytes) as PeerAnnouncement

    assertEquals(decodedEnum.role, decodedString.role)
    assertEquals(decodedEnum.id, decodedString.id)
    assertEquals(decodedEnum.portType, decodedString.portType)
  }
}
