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
}
