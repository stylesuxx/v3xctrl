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
    private external fun nativeFinalize()

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

    fun finalize() {
        nativeFinalize()
    }
}
