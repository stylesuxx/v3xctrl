package com.v3xctrl.viewer.ui.widgets

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay

/**
 * Pipeline timer widget - shows elapsed time since pipeline started.
 * Displays in format HH:MM:SS.mmm with monospace font for stable width.
 */
@Composable
fun PipelineTimer(
    startTimeMs: Long,
    modifier: Modifier = Modifier
) {
    var currentTimeMs by remember { mutableLongStateOf(System.currentTimeMillis()) }

    // Update every 10ms for smooth millisecond display
    LaunchedEffect(Unit) {
        while (true) {
            currentTimeMs = System.currentTimeMillis()
            delay(10)
        }
    }

    val elapsedMs = currentTimeMs - startTimeMs
    val formattedTime = formatElapsedTime(elapsedMs)

    Box(
        modifier = modifier
            .background(
                color = Color.Black.copy(alpha = 0.6f),
                shape = RoundedCornerShape(5.dp)
            )
            .padding(horizontal = 8.dp, vertical = 4.dp)
    ) {
        Text(
            text = formattedTime,
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = 28.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}

/**
 * Format elapsed time as HH:MM:SS.mmm
 */
private fun formatElapsedTime(elapsedMs: Long): String {
    val totalSeconds = elapsedMs / 1000
    val hours = totalSeconds / 3600
    val minutes = (totalSeconds % 3600) / 60
    val seconds = totalSeconds % 60
    val millis = elapsedMs % 1000

    return "%02d:%02d:%02d.%03d".format(hours, minutes, seconds, millis)
}
