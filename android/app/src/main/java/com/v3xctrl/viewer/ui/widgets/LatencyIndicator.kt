package com.v3xctrl.viewer.ui.widgets

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.v3xctrl.viewer.control.LatencyStatus

/**
 * Latency indicator widget - circular dot colored by latency status.
 * Shows connection quality based on RTT/2 measurement:
 * - Green: <= 40ms (excellent)
 * - Yellow: 41-75ms (acceptable)
 * - Red: > 75ms (poor)
 * - Gray: unknown
 */
@Composable
fun LatencyIndicator(
    latencyStatus: LatencyStatus,
    modifier: Modifier = Modifier,
    alpha: Float = 0.7f,
    size: Int = 16
) {
    Box(
        modifier = modifier
            .size(size.dp)
            .background(
                color = latencyStatus.color.copy(alpha = alpha),
                shape = CircleShape
            )
    )
}
