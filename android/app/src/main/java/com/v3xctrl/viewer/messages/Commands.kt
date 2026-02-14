package com.v3xctrl.viewer.messages

/**
 * Factory object for creating common Command messages.
 */
object Commands {
    fun videoStart() = Command(command = "service", parameters = mapOf("action" to "start", "name" to "v3xctrl-video"))
    fun videoStop() = Command(command = "service", parameters = mapOf("action" to "stop", "name" to "v3xctrl-video"))
    fun recordingStart() = Command(command = "recording", parameters = mapOf("action" to "start"))
    fun recordingStop() = Command(command = "recording", parameters = mapOf("action" to "stop"))
    fun trimIncrease() = Command(command = "trim", parameters = mapOf("action" to "increase"))
    fun trimDecrease() = Command(command = "trim", parameters = mapOf("action" to "decrease"))
    fun shutdown() = Command(command = "shutdown")
    fun restart() = Command(command = "restart")
}
