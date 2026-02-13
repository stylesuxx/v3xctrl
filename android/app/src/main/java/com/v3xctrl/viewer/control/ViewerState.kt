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

    fun onControlMessageReceived() {
        lastMessageTimeMs = System.currentTimeMillis()
    }

    fun isConnectionTimedOut(): Boolean {
        if (lastMessageTimeMs == 0L) {
            return false
        }

        return System.currentTimeMillis() - lastMessageTimeMs > connectionTimeoutMs
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
     * Parses byte-packed flags from svc and gst fields.
     */
    fun updateFromTelemetry(values: Map<String, Any>) {
        // Parse svc (service) flags
        val svc = (values["svc"] as? Number)?.toInt() ?: 0
        isVideoRunning = (svc and SVC_VIDEO_BIT) != 0

        // Parse gst (gstreamer) flags
        val gst = (values["gst"] as? Number)?.toInt() ?: 0
        isRecording = (gst and GST_RECORDING_BIT) != 0
    }
}
