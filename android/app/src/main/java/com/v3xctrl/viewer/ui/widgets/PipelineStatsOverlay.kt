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

    LaunchedEffect(Unit) {
        while (true) {
            val stats = GstViewer.getPipelineStats()
            statsText = "src=${stats.udpsrc} jbuf=${stats.jitterbuffer}\n" +
                "depay=${stats.depay} dec=${stats.decoder} sink=${stats.sink}"
            delay(1000)
        }
    }

    OSDWidgetContainer(
        modifier = modifier,
        padding = PaddingValues(horizontal = 8.dp, vertical = 4.dp)
    ) {
        Text(
            text = statsText,
            color = Color.Yellow,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}
