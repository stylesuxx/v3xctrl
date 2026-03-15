package com.v3xctrl.viewer.input

import org.junit.Assert.assertEquals
import org.junit.Test

class DeadZoneTest {

  @Test
  fun zeroInputReturnsZero() {
    assertEquals(0f, applyDeadZone(0f, 0.1f), 0.0001f)
  }

  @Test
  fun inputBelowDeadZoneReturnsZero() {
    assertEquals(0f, applyDeadZone(0.05f, 0.1f), 0.0001f)
    assertEquals(0f, applyDeadZone(0.099f, 0.1f), 0.0001f)
  }

  @Test
  fun inputAtDeadZoneBoundaryReturnsZero() {
    assertEquals(0f, applyDeadZone(0.1f, 0.1f), 0.01f)
  }

  @Test
  fun inputAboveDeadZoneScalesLinearly() {
    // With deadZone=0.1, input=0.55 should map to (0.55-0.1)/(1-0.1) = 0.5
    assertEquals(0.5f, applyDeadZone(0.55f, 0.1f), 0.001f)
  }

  @Test
  fun fullInputReturnsOne() {
    assertEquals(1f, applyDeadZone(1.0f, 0.1f), 0.0001f)
  }

  @Test
  fun negativeInputMirrorsPositive() {
    val positiveResult = applyDeadZone(0.55f, 0.1f)
    val negativeResult = applyDeadZone(-0.55f, 0.1f)
    assertEquals(-positiveResult, negativeResult, 0.0001f)
  }

  @Test
  fun negativeBelowDeadZoneReturnsZero() {
    assertEquals(0f, applyDeadZone(-0.05f, 0.1f), 0.0001f)
  }

  @Test
  fun zeroDeadZonePassesThrough() {
    assertEquals(0.5f, applyDeadZone(0.5f, 0f), 0.0001f)
    assertEquals(-0.5f, applyDeadZone(-0.5f, 0f), 0.0001f)
    assertEquals(1.0f, applyDeadZone(1.0f, 0f), 0.0001f)
  }
}
