package com.v3xctrl.viewer.control

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/**
 * Holds the current control state (throttle and steering values).
 * Thread-safe state holder that can be read from the control loop.
 */
class ControlState {
    /**
     * Throttle value from -1.0 (reverse) to 1.0 (forward).
     * 0.0 is neutral.
     */
    var throttle by mutableFloatStateOf(0f)

    /**
     * Steering value from -1.0 (left) to 1.0 (right).
     * 0.0 is center.
     */
    var steering by mutableFloatStateOf(0f)

    /**
     * When true, the control loop sends 0 on both channels
     * regardless of actual throttle/steering values.
     */
    var paused by mutableStateOf(false)

    fun reset() {
        throttle = 0f
        steering = 0f
    }
}
