package com.v3xctrl.viewer.control

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color

// Latency status levels based on RTT/2 measurements
enum class LatencyStatus(val color: Color) {
    UNKNOWN(Color.Gray),
    GOOD(Color.Green),         // <= 40ms
    ACCEPTABLE(Color.Yellow),  // 41-75ms
    POOR(Color.Red)            // > 75ms
}

// Telemetry bit flags
private const val SVC_VIDEO_BIT = 0x01
private const val GST_RECORDING_BIT = 0x01

/**
 * Observable state for the viewer UI.
 * Tracks connection status, latency, and telemetry values.
 */
class ViewerState {
    // Connection timeout in milliseconds (5 seconds)
    private val connectionTimeoutMs = 5000L

    @Volatile private var lastMessageTimeMs: Long = 0L

    // Observable state properties
    var isControlConnected by mutableStateOf(false)
    var isVideoRunning by mutableStateOf(false)
    var isRecording by mutableStateOf(false)
    var latencyMs by mutableStateOf<Long?>(null)
    var latencyStatus by mutableStateOf(LatencyStatus.UNKNOWN)

    // Battery telemetry
    var batteryVoltage by mutableStateOf<Int?>(null)
    var batteryAvgVoltage by mutableStateOf<Int?>(null)
    var batteryPercent by mutableStateOf<Int?>(null)
    var batteryWarning by mutableStateOf(false)
    var batteryCurrent by mutableStateOf<Int?>(null)

    // Signal telemetry
    var signalRsrp by mutableStateOf<Int?>(null)
    var signalRsrq by mutableStateOf<Int?>(null)
    var signalBand by mutableStateOf<String?>(null)
    var signalCellId by mutableStateOf<Int?>(null)

    var isControlTimedOut by mutableStateOf(false)

    fun onControlMessageReceived() {
        lastMessageTimeMs = System.currentTimeMillis()
        isControlTimedOut = false
    }

    /**
     * Check whether control messages have stopped arriving.
     * Updates isControlTimedOut reactive state. Returns the current value.
     */
    fun checkControlTimeout(): Boolean {
        if (lastMessageTimeMs != 0L &&
            System.currentTimeMillis() - lastMessageTimeMs > connectionTimeoutMs
        ) {
            isControlTimedOut = true
            latencyStatus = LatencyStatus.UNKNOWN
        }
        return isControlTimedOut
    }

    /**
     * Update latency from an echoed Latency message.
     * The timestamp in the message is the time we sent it.
     */
    fun updateLatency(sentTimestamp: Double) {
        val now = System.currentTimeMillis() / 1000.0
        val rttSeconds = now - sentTimestamp
        val rttMs = (rttSeconds * 1000).toLong()
        val oneWayMs = rttMs / 2

        latencyMs = oneWayMs
        latencyStatus = when {
            oneWayMs <= 40 -> LatencyStatus.GOOD
            oneWayMs <= 75 -> LatencyStatus.ACCEPTABLE
            else -> LatencyStatus.POOR
        }
    }

    /**
     * Update state from telemetry values.
     * Parses byte-packed flags from svc and gst fields, and battery data from bat map.
     */
    @Suppress("UNCHECKED_CAST")
    fun updateFromTelemetry(values: Map<String, Any>) {
        // Parse svc (service) flags
        val svc = (values["svc"] as? Number)?.toInt() ?: 0
        isVideoRunning = (svc and SVC_VIDEO_BIT) != 0

        // Parse gst (gstreamer) flags
        val gst = (values["gst"] as? Number)?.toInt() ?: 0
        isRecording = (gst and GST_RECORDING_BIT) != 0

        // Parse battery telemetry
        val bat = values["bat"] as? Map<String, Any>
        if (bat != null) {
            batteryVoltage = (bat["vol"] as? Number)?.toInt()
            batteryAvgVoltage = (bat["avg"] as? Number)?.toInt()
            batteryPercent = (bat["pct"] as? Number)?.toInt()
            batteryWarning = (bat["wrn"] as? Number)?.toInt() == 1
            batteryCurrent = (bat["cur"] as? Number)?.toInt()
        }

        // Parse signal telemetry
        val sig = values["sig"] as? Map<String, Any>
        if (sig != null) {
            signalRsrp = (sig["rsrp"] as? Number)?.toInt()
            signalRsrq = (sig["rsrq"] as? Number)?.toInt()
        }

        val cell = values["cell"] as? Map<String, Any>
        if (cell != null) {
            signalBand = (cell["band"] as? Number)?.toString()
                ?: (cell["band"] as? String)
            signalCellId = (cell["id"] as? Number)?.toInt()
        }
    }
}
