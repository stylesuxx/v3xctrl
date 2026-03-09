package com.v3xctrl.viewer.ui.widgets

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import android.os.Debug
import android.os.Process
import android.os.SystemClock
import com.v3xctrl.viewer.GstViewer
import kotlinx.coroutines.delay

private val LabelColor = Color.Gray
private val ValueColor = Color.White
private val HeaderColor = Color.Yellow

@Composable
fun DebugStatsOverlay(
    showPipelineStats: Boolean,
    showSystemStats: Boolean,
    modifier: Modifier = Modifier
) {
    var stats by remember { mutableStateOf(GstViewer.PipelineStats(0, 0, 0, 0, 0, 0)) }
    var decoderName by remember { mutableStateOf("") }
    var decodeQueueLevel by remember { mutableStateOf(0) }
    var renderQueueLevel by remember { mutableStateOf(0) }
    var cpuUsage by remember { mutableStateOf<Int?>(null) }
    var nativeHeapMb by remember { mutableStateOf(0f) }
    var javaHeapMb by remember { mutableStateOf(0f) }

    LaunchedEffect(showPipelineStats, showSystemStats) {
        var previousCpuTime = Process.getElapsedCpuTime()
        var previousWallTime = SystemClock.elapsedRealtime()
        while (true) {
            if (showPipelineStats) {
                stats = GstViewer.getPipelineStats()
                decodeQueueLevel = GstViewer.decodeQueueLevel
                renderQueueLevel = GstViewer.renderQueueLevel
            }

            decoderName = GstViewer.decoderName

            if (showSystemStats) {
                val currentCpuTime = Process.getElapsedCpuTime()
                val currentWallTime = SystemClock.elapsedRealtime()
                val wallDelta = currentWallTime - previousWallTime
                if (wallDelta > 0) {
                    val cpuDelta = currentCpuTime - previousCpuTime
                    cpuUsage = (cpuDelta * 100 / wallDelta).toInt()
                }
                previousCpuTime = currentCpuTime
                previousWallTime = currentWallTime

                nativeHeapMb = Debug.getNativeHeapAllocatedSize() / (1024f * 1024f)
                val runtime = Runtime.getRuntime()
                javaHeapMb = (runtime.totalMemory() - runtime.freeMemory()) / (1024f * 1024f)
            }

            delay(1000)
        }
    }

    OSDWidgetContainer(
        modifier = modifier,
        padding = PaddingValues(horizontal = 12.dp, vertical = 8.dp)
    ) {
        Column {
            if (showPipelineStats) {
                // Buffer counts table
                Row {
                    StatsColumn("src", stats.udpsrc, modifier = Modifier.weight(1f))
                    StatsColumn("jbuf", stats.jitterbuffer, modifier = Modifier.weight(1f))
                    StatsColumn("depay", stats.depay, modifier = Modifier.weight(1f))
                    StatsColumn("dec", stats.decoder, modifier = Modifier.weight(1f))
                    StatsColumn("sink", stats.sink, modifier = Modifier.weight(1f))
                    StatsColumn("drop", stats.dropped, if (stats.dropped > 0) Color.Red else ValueColor, Modifier.weight(1f))
                }

                HorizontalDivider(
                    color = Color.Gray.copy(alpha = 0.4f),
                    modifier = Modifier.padding(vertical = 6.dp)
                )

                StatsRow("decode queue", "$decodeQueueLevel/3",
                    if (decodeQueueLevel >= 2) Color.Red else ValueColor)
                StatsRow("render queue", "$renderQueueLevel/1",
                    if (renderQueueLevel >= 1) Color.Red else ValueColor)
            }

            if (showPipelineStats && showSystemStats) {
                HorizontalDivider(
                    color = Color.Gray.copy(alpha = 0.4f),
                    modifier = Modifier.padding(vertical = 6.dp)
                )
            }

            if (showSystemStats) {
                if (decoderName.isNotEmpty()) {
                    StatsRow("decoder", decoderName, ValueColor)
                }
                cpuUsage?.let { cpu ->
                    StatsRow("cpu", "$cpu%", if (cpu > 80) Color.Red else ValueColor)
                }
                StatsRow("mem native", "%.1f MB".format(nativeHeapMb))
                StatsRow("mem java", "%.1f MB".format(javaHeapMb))
            }
        }
    }
}

@Composable
private fun StatsColumn(
    label: String,
    value: Int,
    valueColor: Color = ValueColor,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        Text(
            text = label,
            color = HeaderColor,
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold
        )
        Text(
            text = value.toString(),
            color = valueColor,
            fontSize = 12.sp,
            fontFamily = FontFamily.Monospace,
            modifier = Modifier.align(Alignment.Start)
        )
    }
}

@Composable
private fun StatsRow(label: String, value: String, valueColor: Color = ValueColor) {
    Row {
        Text(
            text = "$label: ",
            color = LabelColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace
        )
        Text(
            text = value,
            color = valueColor,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace
        )
    }
}
