package com.v3xctrl.viewer.input

import kotlin.math.abs

fun applyDeadZone(value: Float, deadZone: Float): Float {
    if (abs(value) < deadZone) return 0f
    val sign = if (value > 0) 1f else -1f
    return sign * (abs(value) - deadZone) / (1f - deadZone)
}
