package com.v3xctrl.viewer.ui.widgets

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.v3xctrl.viewer.GstViewer
import kotlinx.coroutines.delay

@Composable
fun PipelineStatsOverlay(
    modifier: Modifier = Modifier
) {
    var statsText by remember { mutableStateOf("") }

    var droppingFrames by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        while (true) {
            val stats = GstViewer.getPipelineStats()
            val decoder = GstViewer.decoderName
            droppingFrames = stats.dropped > 0
            statsText = "src=${stats.udpsrc} jbuf=${stats.jitterbuffer}\n" +
                "depay=${stats.depay} dec=${stats.decoder} sink=${stats.sink}" +
                (if (droppingFrames) "\ndropped=${stats.dropped}" else "") +
                (if (decoder.isNotEmpty()) "\ndecoder=$decoder" else "")
            delay(1000)
        }
    }

    OSDWidgetContainer(
        modifier = modifier,
        padding = PaddingValues(horizontal = 8.dp, vertical = 4.dp)
    ) {
        Text(
            text = statsText,
            color = if (droppingFrames) Color.Red else Color.Yellow,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}
