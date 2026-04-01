package com.v3xctrl.viewer

import android.view.Surface

object GstViewer {
    init {
        System.loadLibrary("v3xctrl_gst")
    }

    private external fun nativeInit()
    private external fun nativeStartPipeline(surface: Surface, port: Int)
    private external fun nativeStopPipeline()
    private external fun nativeGetRestartCount(): Int
    private external fun nativeGetFrameCount(): Int
    private external fun nativeRestartPipeline()
    private external fun nativePausePipeline()
    private external fun nativeResumePipeline(surface: Surface)
    private external fun nativeFinalize()
    private external fun nativeSetStatsEnabled(enabled: Boolean)
    private external fun nativeGetPipelineStats(): String
    private external fun nativeGetDecodeQueueLevel(): Int
    private external fun nativeGetRenderQueueLevel(): Int
    private external fun nativeGetDecoderName(): String
    private external fun nativeGetFrameIntervalStats(): String
    private external fun nativeGetJitterBufferStats(): String
    private external fun nativeGetDecoderOutputFormat(): String

    fun init() {
        nativeInit()
    }

    fun start(surface: Surface, videoPort: Int) {
        nativeStartPipeline(surface, videoPort)
    }

    fun stop() {
        nativeStopPipeline()
    }

    val restartCount: Int get() = nativeGetRestartCount()
    val frameCount: Int get() = nativeGetFrameCount()

    fun restart() {
        nativeRestartPipeline()
    }

    fun pause() {
        nativePausePipeline()
    }

    fun resume(surface: Surface) {
        nativeResumePipeline(surface)
    }

    fun setStatsEnabled(enabled: Boolean) {
        nativeSetStatsEnabled(enabled)
    }

    data class PipelineStats(
        val udpsrc: Int,
        val jitterbuffer: Int,
        val depay: Int,
        val decoder: Int,
        val sink: Int,
        val dropped: Int
    )

    fun getPipelineStats(): PipelineStats {
        val parts = nativeGetPipelineStats().split("|", limit = 6)
        return PipelineStats(
            udpsrc = parts.getOrNull(0)?.toIntOrNull() ?: 0,
            jitterbuffer = parts.getOrNull(1)?.toIntOrNull() ?: 0,
            depay = parts.getOrNull(2)?.toIntOrNull() ?: 0,
            decoder = parts.getOrNull(3)?.toIntOrNull() ?: 0,
            sink = parts.getOrNull(4)?.toIntOrNull() ?: 0,
            dropped = parts.getOrNull(5)?.toIntOrNull() ?: 0
        )
    }

    val decodeQueueLevel: Int get() = nativeGetDecodeQueueLevel()
    val renderQueueLevel: Int get() = nativeGetRenderQueueLevel()
    val decoderName: String get() = nativeGetDecoderName()
    val decoderOutputFormat: String get() = nativeGetDecoderOutputFormat()

    data class FrameIntervalStats(
        val averageUs: Long,
        val minUs: Long,
        val maxUs: Long
    )

    fun getFrameIntervalStats(): FrameIntervalStats {
        val parts = nativeGetFrameIntervalStats().split("|", limit = 3)
        return FrameIntervalStats(
            averageUs = parts.getOrNull(0)?.toLongOrNull() ?: 0,
            minUs = parts.getOrNull(1)?.toLongOrNull() ?: 0,
            maxUs = parts.getOrNull(2)?.toLongOrNull() ?: 0
        )
    }

    data class JitterBufferStats(
        val pushed: Long,
        val lost: Long,
        val late: Long,
        val duplicates: Long
    )

    fun getJitterBufferStats(): JitterBufferStats {
        val parts = nativeGetJitterBufferStats().split("|", limit = 4)
        return JitterBufferStats(
            pushed = parts.getOrNull(0)?.toLongOrNull() ?: 0,
            lost = parts.getOrNull(1)?.toLongOrNull() ?: 0,
            late = parts.getOrNull(2)?.toLongOrNull() ?: 0,
            duplicates = parts.getOrNull(3)?.toLongOrNull() ?: 0
        )
    }

    fun finalize() {
        nativeFinalize()
    }
}
