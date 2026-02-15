package com.v3xctrl.viewer.input

import android.view.InputDevice
import android.view.MotionEvent
import com.v3xctrl.viewer.control.ControlState

/**
 * Gamepad controller that handles USB and Bluetooth HID game controllers.
 * Uses calibrated axis mappings to map physical axes to steering and throttle.
 * Call [handleMotionEvent] from Activity.dispatchGenericMotionEvent.
 */
class GamepadController(
    private val controlState: ControlState,
    private val deviceId: Int? = null,
    private val steeringAxis: Int = MotionEvent.AXIS_X,
    private val steeringSign: Int = 1,
    private val throttleAxis: Int = MotionEvent.AXIS_Y,
    private val throttleSign: Int = -1,
    private val reverseAxis: Int = MotionEvent.AXIS_Y,
    private val reverseSign: Int = 1,
    private val steeringInvert: Boolean = false,
    private val throttleInvert: Boolean = false,
    private val reverseInvert: Boolean = false,
    private val deadZone: Float = 0.1f
) {

    fun handleMotionEvent(event: MotionEvent): Boolean {
        if (event.source and InputDevice.SOURCE_JOYSTICK == InputDevice.SOURCE_JOYSTICK &&
            event.action == MotionEvent.ACTION_MOVE &&
            (deviceId == null || event.deviceId == deviceId)
        ) {
            val steeringMul = steeringSign * (if (steeringInvert) -1 else 1)
            val throttleMul = throttleSign * (if (throttleInvert) -1 else 1)
            val reverseMul = reverseSign * (if (reverseInvert) -1 else 1)

            val rawSteering = (event.getAxisValue(steeringAxis) * steeringMul)
                .coerceIn(-1f, 1f)

            val rawThrottle = if (throttleAxis == reverseAxis) {
                (event.getAxisValue(throttleAxis) * throttleMul).coerceIn(-1f, 1f)
            } else {
                val forward = (event.getAxisValue(throttleAxis) * throttleMul)
                    .coerceAtLeast(0f)
                val backward = (event.getAxisValue(reverseAxis) * reverseMul)
                    .coerceAtLeast(0f)
                (forward - backward).coerceIn(-1f, 1f)
            }

            controlState.steering = applyDeadZone(rawSteering, deadZone)
            controlState.throttle = applyDeadZone(rawThrottle, deadZone)

            return true
        }

        return false
    }
}
