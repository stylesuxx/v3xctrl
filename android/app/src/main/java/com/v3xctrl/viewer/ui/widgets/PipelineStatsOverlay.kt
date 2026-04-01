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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.File

private val LabelColor = Color.Gray
private val ValueColor = Color.White
private val HeaderColor = Color.Yellow

private data class ThreadCpuSnapshot(
    val tid: Int,
    val name: String,
    val cpuTicks: Long
)

private data class ThreadCpuUsage(
    val name: String,
    val percent: Int
)

private fun readThreadCpuSnapshots(): List<ThreadCpuSnapshot> {
    val taskDir = File("/proc/self/task")
    if (!taskDir.isDirectory) {
        return emptyList()
    }
    return taskDir.listFiles()?.mapNotNull { tidDir ->
        val tid = tidDir.name.toIntOrNull() ?: return@mapNotNull null
        val statFile = File(tidDir, "stat")
        val commFile = File(tidDir, "comm")
        try {
            val name = commFile.readText().trim()
            val statFields = statFile.readText().split(" ")
            // Fields 13 and 14 (0-indexed) are utime and stime in clock ticks
            if (statFields.size > 14) {
                val utime = statFields[13].toLongOrNull() ?: 0L
                val stime = statFields[14].toLongOrNull() ?: 0L
                ThreadCpuSnapshot(tid, name, utime + stime)
            } else {
                null
            }
        } catch (_: Exception) {
            null
        }
    } ?: emptyList()
}

private fun computeThreadCpuUsage(
    previous: List<ThreadCpuSnapshot>,
    current: List<ThreadCpuSnapshot>,
    wallDeltaMs: Long
): List<ThreadCpuUsage> {
    if (wallDeltaMs <= 0) {
        return emptyList()
    }
    val prevMap = previous.associateBy { it.tid }
    val ticksPerSec = 100L // standard Linux HZ
    return current.mapNotNull { curr ->
        val prev = prevMap[curr.tid] ?: return@mapNotNull null
        val tickDelta = curr.cpuTicks - prev.cpuTicks
        val cpuMs = tickDelta * 1000 / ticksPerSec
        val percent = (cpuMs * 100 / wallDeltaMs).toInt()
        if (percent > 0) {
            ThreadCpuUsage(curr.name, percent)
        } else {
            null
        }
    }.sortedByDescending { it.percent }
}

@Composable
fun DebugStatsOverlay(
    showPipelineStats: Boolean,
    showSystemStats: Boolean,
    modifier: Modifier = Modifier
) {
    var stats by remember { mutableStateOf(GstViewer.PipelineStats(0, 0, 0, 0, 0, 0)) }
    var decoderName by remember { mutableStateOf("") }
    var decoderOutputFormat by remember { mutableStateOf("") }
    var decodeQueueLevel by remember { mutableStateOf(0) }
    var renderQueueLevel by remember { mutableStateOf(0) }
    var frameInterval by remember { mutableStateOf(GstViewer.FrameIntervalStats(0, 0, 0)) }
    var jitterBufferStats by remember { mutableStateOf(GstViewer.JitterBufferStats(0, 0, 0, 0)) }
    var cpuUsage by remember { mutableStateOf<Int?>(null) }
    var topThreads by remember { mutableStateOf<List<ThreadCpuUsage>>(emptyList()) }
    var nativeHeapMb by remember { mutableStateOf(0f) }
    var javaHeapMb by remember { mutableStateOf(0f) }

    LaunchedEffect(showPipelineStats, showSystemStats) {
        var previousCpuTime = Process.getElapsedCpuTime()
        var previousWallTime = SystemClock.elapsedRealtime()
        var previousThreadSnapshots = emptyList<ThreadCpuSnapshot>()
        while (true) {
            if (showPipelineStats) {
                stats = GstViewer.getPipelineStats()
                decodeQueueLevel = GstViewer.decodeQueueLevel
                renderQueueLevel = GstViewer.renderQueueLevel
                frameInterval = GstViewer.getFrameIntervalStats()
                jitterBufferStats = GstViewer.getJitterBufferStats()
            }

            decoderName = GstViewer.decoderName
            decoderOutputFormat = GstViewer.decoderOutputFormat

            if (showSystemStats) {
                val currentCpuTime = Process.getElapsedCpuTime()
                val currentWallTime = SystemClock.elapsedRealtime()
                val wallDelta = currentWallTime - previousWallTime
                if (wallDelta > 0) {
                    val cpuDelta = currentCpuTime - previousCpuTime
                    cpuUsage = (cpuDelta * 100 / wallDelta).toInt()
                }

                val currentThreadSnapshots = withContext(Dispatchers.IO) {
                    readThreadCpuSnapshots()
                }
                if (previousThreadSnapshots.isNotEmpty()) {
                    topThreads = computeThreadCpuUsage(
                        previousThreadSnapshots, currentThreadSnapshots, wallDelta
                    ).take(5)
                }
                previousThreadSnapshots = currentThreadSnapshots

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

                HorizontalDivider(
                    color = Color.Gray.copy(alpha = 0.4f),
                    modifier = Modifier.padding(vertical = 6.dp)
                )

                // Frame interval timing with target FPS detection
                val avgMs = frameInterval.averageUs / 1000f
                val minMs = frameInterval.minUs / 1000f
                val maxMs = frameInterval.maxUs / 1000f
                val targetFps: Int
                val targetMs: Float
                val toleranceMs = 3f
                if (avgMs in (16.6f - toleranceMs)..(16.6f + toleranceMs)) {
                    targetFps = 60
                    targetMs = 16.6f
                } else {
                    targetFps = 30
                    targetMs = 33.3f
                }
                val intervalColor = when {
                    avgMs <= 0f -> ValueColor
                    avgMs <= targetMs + toleranceMs -> Color.Green
                    avgMs <= targetMs * 1.5f -> Color.Yellow
                    else -> Color.Red
                }
                StatsRow("frame interval",
                    "%.1f ms (%.1f-%.1f) [${targetFps}fps]".format(avgMs, minMs, maxMs),
                    intervalColor)

                // Jitter buffer stats
                val jbufLossColor = if (jitterBufferStats.lost > 0 || jitterBufferStats.late > 0) {
                    Color.Red
                } else {
                    ValueColor
                }
                StatsRow("jbuf lost/late",
                    "${jitterBufferStats.lost}/${jitterBufferStats.late}",
                    jbufLossColor)
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
                if (decoderOutputFormat.isNotEmpty()) {
                    StatsRow("output format", decoderOutputFormat, ValueColor)
                }
                cpuUsage?.let { cpu ->
                    StatsRow("cpu (process)", "$cpu%", if (cpu > 80) Color.Red else ValueColor)
                }
                for (thread in topThreads) {
                    StatsRow("  ${thread.name}", "${thread.percent}%",
                        if (thread.percent > 50) Color.Red else ValueColor)
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
