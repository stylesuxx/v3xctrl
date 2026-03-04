package com.v3xctrl.viewer.ui.widgets

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.v3xctrl.viewer.GstViewer
import kotlinx.coroutines.delay

private const val WINDOW_SIZE = 5

@Composable
fun FpsCounter(
    modifier: Modifier = Modifier
) {
    var fps by remember { mutableIntStateOf(0) }

    LaunchedEffect(Unit) {
        val timestamps = LongArray(WINDOW_SIZE + 1)
        val frameCounts = IntArray(WINDOW_SIZE + 1)
        var head = 0
        var count = 0

        while (true) {
            val currentFrameCount = GstViewer.frameCount
            val prev = if (count > 0) {
                (head - 1 + timestamps.size) % timestamps.size
            } else {
                head
            }

            // Pipeline restart detected — counter went backwards; clear the buffer
            if (count > 0 && currentFrameCount < frameCounts[prev]) {
                head = 0
                count = 0
                fps = 0
            }

            timestamps[head] = System.currentTimeMillis()
            frameCounts[head] = currentFrameCount

            if (count < timestamps.size) count++

            if (count >= 2) {
                val oldest = (head - count + 1 + timestamps.size) % timestamps.size
                val dtMs = timestamps[head] - timestamps[oldest]
                val dFrames = frameCounts[head] - frameCounts[oldest]
                if (dtMs > 0) {
                    fps = (dFrames * 1000L / dtMs).toInt()
                }
            }

            head = (head + 1) % timestamps.size
            delay(1000)
        }
    }

    OSDWidgetContainer(
        modifier = modifier,
        padding = PaddingValues(horizontal = 8.dp, vertical = 4.dp)
    ) {
        Text(
            text = "$fps fps",
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = 14.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}
