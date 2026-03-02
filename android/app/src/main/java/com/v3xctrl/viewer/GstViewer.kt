package com.v3xctrl.viewer

import android.view.Surface

object GstViewer {
    init {
        System.loadLibrary("v3xctrl_gst")
    }

    private external fun nativeInit()
    private external fun nativeStartPipeline(surface: Surface, port: Int)
    private external fun nativeStopPipeline()
    private external fun nativeFinalize()
    private external fun nativeGetStats(): String

    fun init() {
        nativeInit()
    }

    fun start(surface: Surface, videoPort: Int) {
        nativeStartPipeline(surface, videoPort)
    }

    fun stop() {
        nativeStopPipeline()
    }

    fun finalize() {
        nativeFinalize()
    }

    /**
     * Returns pipeline diagnostics: packet count, byte count, and last
     * source address seen by udpsrc.
     */
    fun getStats(): PipelineStats {
        val raw = nativeGetStats()
        val parts = raw.split("|", limit = 8)
        return PipelineStats(
            packets = parts.getOrNull(0)?.toLongOrNull() ?: 0,
            bytes = parts.getOrNull(1)?.toLongOrNull() ?: 0,
            lastSource = parts.getOrNull(2)?.ifEmpty { null },
            pipelineState = parts.getOrNull(3) ?: "?",
            localPort = parts.getOrNull(4)?.toIntOrNull() ?: 0,
            jbPushed = parts.getOrNull(5)?.toLongOrNull() ?: -1,
            jbLost = parts.getOrNull(6)?.toLongOrNull() ?: -1,
            jbLate = parts.getOrNull(7)?.toLongOrNull() ?: -1
        )
    }

    data class PipelineStats(
        val packets: Long,
        val bytes: Long,
        val lastSource: String?,
        val pipelineState: String,
        val localPort: Int,
        val jbPushed: Long,
        val jbLost: Long,
        val jbLate: Long
    )
}
