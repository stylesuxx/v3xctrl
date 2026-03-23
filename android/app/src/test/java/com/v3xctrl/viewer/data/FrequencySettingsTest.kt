package com.v3xctrl.viewer.data

import org.junit.Assert.assertEquals
import org.junit.Test

class FrequencySettingsTest {

  @Test
  fun `default values are correct`() {
    val settings = FrequencySettings()
    assertEquals(30, settings.controlHz)
    assertEquals(1, settings.controlBufferCapacity)
  }

  @Test
  fun `copy with controlBufferCapacity`() {
    val settings = FrequencySettings()
    val updated = settings.copy(controlBufferCapacity = 5)
    assertEquals(5, updated.controlBufferCapacity)
    assertEquals(30, updated.controlHz)
  }

  @Test
  fun `copy with both fields`() {
    val settings = FrequencySettings(controlHz = 60, controlBufferCapacity = 10)
    assertEquals(60, settings.controlHz)
    assertEquals(10, settings.controlBufferCapacity)
  }
}
