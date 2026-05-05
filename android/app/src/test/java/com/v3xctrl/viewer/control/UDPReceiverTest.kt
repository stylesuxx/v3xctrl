package com.v3xctrl.viewer.control

import com.v3xctrl.viewer.messages.Control
import org.junit.Assert.assertEquals
import org.junit.Test

class UDPReceiverTest {

  private fun Control.throttle(): Double = values["throttle"] as Double
  private fun Control.steering(): Double = values["steering"] as Double

  @Test
  fun `resolveControlMessage returns zero when controlsActive is false`() {
    val state = ControlState().apply {
      throttle = 0.7f
      steering = -0.5f
    }

    val result = resolveControlMessage(
      state = state,
      controlsActive = false,
      forwardScale = 1f,
      backwardScale = 1f,
      steeringScale = 1f
    )

    assertEquals(0.0, result.throttle(), 0.0)
    assertEquals(0.0, result.steering(), 0.0)
  }

  @Test
  fun `resolveControlMessage returns zero when paused`() {
    val state = ControlState().apply {
      throttle = 0.4f
      steering = 0.6f
      paused = true
    }

    val result = resolveControlMessage(
      state = state,
      controlsActive = true,
      forwardScale = 1f,
      backwardScale = 1f,
      steeringScale = 1f
    )

    assertEquals(0.0, result.throttle(), 0.0)
    assertEquals(0.0, result.steering(), 0.0)
  }

  @Test
  fun `resolveControlMessage returns zero when both paused and inactive`() {
    val state = ControlState().apply {
      throttle = 1f
      steering = 1f
      paused = true
    }

    val result = resolveControlMessage(
      state = state,
      controlsActive = false,
      forwardScale = 1f,
      backwardScale = 1f,
      steeringScale = 1f
    )

    assertEquals(0.0, result.throttle(), 0.0)
    assertEquals(0.0, result.steering(), 0.0)
  }

  @Test
  fun `resolveControlMessage applies forwardScale to positive throttle`() {
    val state = ControlState().apply {
      throttle = 0.8f
      steering = 0f
    }

    val result = resolveControlMessage(
      state = state,
      controlsActive = true,
      forwardScale = 0.5f,
      backwardScale = 1f,
      steeringScale = 1f
    )

    assertEquals(0.4, result.throttle(), 1e-6)
    assertEquals(0.0, result.steering(), 0.0)
  }

  @Test
  fun `resolveControlMessage applies backwardScale to negative throttle`() {
    val state = ControlState().apply {
      throttle = -0.6f
      steering = 0f
    }

    val result = resolveControlMessage(
      state = state,
      controlsActive = true,
      forwardScale = 1f,
      backwardScale = 0.5f,
      steeringScale = 1f
    )

    assertEquals(-0.3, result.throttle(), 1e-6)
    assertEquals(0.0, result.steering(), 0.0)
  }

  @Test
  fun `resolveControlMessage applies steeringScale`() {
    val state = ControlState().apply {
      throttle = 0f
      steering = -0.8f
    }

    val result = resolveControlMessage(
      state = state,
      controlsActive = true,
      forwardScale = 1f,
      backwardScale = 1f,
      steeringScale = 0.25f
    )

    assertEquals(0.0, result.throttle(), 0.0)
    assertEquals(-0.2, result.steering(), 1e-6)
  }

  @Test
  fun `resolveControlMessage returns zero for null state`() {
    val result = resolveControlMessage(
      state = null,
      controlsActive = true,
      forwardScale = 1f,
      backwardScale = 1f,
      steeringScale = 1f
    )

    assertEquals(0.0, result.throttle(), 0.0)
    assertEquals(0.0, result.steering(), 0.0)
  }
}
