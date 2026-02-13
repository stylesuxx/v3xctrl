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
    private val deadZone: Float = 0.1f
) {

    fun handleMotionEvent(event: MotionEvent): Boolean {
        if (event.source and InputDevice.SOURCE_JOYSTICK == InputDevice.SOURCE_JOYSTICK &&
            event.action == MotionEvent.ACTION_MOVE &&
            (deviceId == null || event.deviceId == deviceId)
        ) {
            val rawSteering = (event.getAxisValue(steeringAxis) * steeringSign)
                .coerceIn(-1f, 1f)

            val rawThrottle = if (throttleAxis == reverseAxis) {
                (event.getAxisValue(throttleAxis) * throttleSign).coerceIn(-1f, 1f)
            } else {
                val forward = (event.getAxisValue(throttleAxis) * throttleSign)
                    .coerceAtLeast(0f)
                val backward = (event.getAxisValue(reverseAxis) * reverseSign)
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
