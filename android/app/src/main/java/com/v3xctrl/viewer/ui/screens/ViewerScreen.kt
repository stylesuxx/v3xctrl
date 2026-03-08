package com.v3xctrl.viewer.ui.screens

import android.app.Activity
import android.content.pm.ActivityInfo
import android.widget.Toast
import android.content.Context
import android.content.res.Configuration
import android.net.wifi.WifiManager
import android.os.Build
import android.view.InputDevice
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.WindowManager
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import com.v3xctrl.viewer.MainActivity
import com.v3xctrl.viewer.GstViewer
import com.v3xctrl.viewer.control.ControlState
import com.v3xctrl.viewer.data.ControlSettings
import com.v3xctrl.viewer.data.OsdSettings
import com.v3xctrl.viewer.data.Transport
import com.v3xctrl.viewer.input.GamepadController
import com.v3xctrl.viewer.input.MotionController
import com.v3xctrl.viewer.control.UDPReceiver
import com.v3xctrl.viewer.control.VideoPortKeepAlive
import com.v3xctrl.viewer.control.ViewerState
import com.v3xctrl.viewer.R
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.net.DatagramSocket
import java.net.InetAddress

data class ConnectionInfo(
    val videoPort: Int,
    val controlPort: Int,
    val relayHost: String,
    val relayPort: Int,
    val sessionId: String,
    val transport: Transport = Transport.UDP
)

@Composable
fun ViewerScreen(
    connection: ConnectionInfo,
    controlHz: Int = 30,
    osdSettings: OsdSettings = OsdSettings(),
    showPipelineStats: Boolean = false,
    spectatorMode: Boolean = false,
    controlSettings: ControlSettings = ControlSettings(),
    isInPipMode: Boolean = false,
    onBack: () -> Unit,
    onNavigateToGeneral: () -> Unit = {},
    onNavigateToNetwork: () -> Unit = {},
    onNavigateToFrequencies: () -> Unit = {},
    onNavigateToOSD: () -> Unit = {},
    onNavigateToControl: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val configuration = LocalConfiguration.current
    val isLandscape = configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
    val scope = rememberCoroutineScope()

    // Control state for throttle and steering
    val controlState = remember { ControlState() }

    // Viewer state for connection tracking and telemetry
    val viewerState = remember { ViewerState() }

    // UDPReceiver reference for sending commands
    var udpReceiver by remember { mutableStateOf<UDPReceiver?>(null) }

    // Track if video should be blanked (after 5 seconds of video service stopped)
    var showVideoBlank by remember { mutableStateOf(false) }

    // Track whether the pipeline has been started (survives surface recreation on rotation)
    var isPipelineStarted by remember { mutableStateOf(false) }

    // Pipeline start time for timer widget
    val pipelineStartTime = remember { System.currentTimeMillis() }

    // FPS counter - hoisted here so it survives orientation changes
    var fps by remember { mutableIntStateOf(0) }

    LaunchedEffect(Unit) {
        val windowSize = 5
        val timestamps = LongArray(windowSize + 1)
        val frameCounts = IntArray(windowSize + 1)
        var head = 0
        var count = 0

        while (true) {
            val currentFrameCount = GstViewer.frameCount
            val prev = if (count > 0) {
                (head - 1 + timestamps.size) % timestamps.size
            } else {
                head
            }

            // Pipeline restart detected - counter went backwards; clear the buffer
            if (count > 0 && currentFrameCount < frameCounts[prev]) {
                head = 0
                count = 0
                fps = 0
            }

            timestamps[head] = System.currentTimeMillis()
            frameCounts[head] = currentFrameCount

            if (count < timestamps.size) {
                count++
            }

            if (count >= 2) {
                val oldest = (head - count + 1 + timestamps.size) % timestamps.size
                val dtMs = timestamps[head] - timestamps[oldest]
                val dFrames = frameCounts[head] - frameCounts[oldest]
                if (dtMs > 0) {
                    fps = ((dFrames * 1000L + dtMs - 1) / dtMs).toInt()
                }
            }

            head = (head + 1) % timestamps.size
            delay(1000)
        }
    }

    // Reset controls when entering PiP so the vehicle stops
    LaunchedEffect(isInPipMode) {
        if (isInPipMode) {
            controlState.reset()
        }
    }

    // Motion controller for gyroscope-based control
    val isMotionMode = controlSettings.controlMode == "motion" && !spectatorMode
    var motionController by remember { mutableStateOf<MotionController?>(null) }

    // Gamepad controller for USB/Bluetooth HID controllers
    val isGamepadMode = controlSettings.controlMode == "gamepad" && !spectatorMode

    // Start/stop motion controller based on mode and orientation (disabled in PiP)
    DisposableEffect(isMotionMode, isLandscape, isInPipMode, controlSettings.motionSteeringDeg, controlSettings.motionForwardDeg, controlSettings.motionBackwardDeg, controlSettings.motionSteeringInvert, controlSettings.motionThrottleInvert) {
        if (isMotionMode && isLandscape && !isInPipMode) {
            val controller = MotionController(
                context = context,
                controlState = controlState,
                steeringDeg = controlSettings.motionSteeringDeg.toFloat(),
                forwardDeg = controlSettings.motionForwardDeg.toFloat(),
                backwardDeg = controlSettings.motionBackwardDeg.toFloat(),
                steeringInvert = controlSettings.motionSteeringInvert,
                throttleInvert = controlSettings.motionThrottleInvert
            )
            controller.start()
            motionController = controller
        }
        onDispose {
            motionController?.stop()
            motionController = null
        }
    }

    // Start/stop gamepad controller based on mode and orientation
    DisposableEffect(isGamepadMode, isLandscape, controlSettings.gamepadDeviceName, controlSettings.gamepadSteeringAxis, controlSettings.gamepadSteeringSign, controlSettings.gamepadThrottleAxis, controlSettings.gamepadThrottleSign, controlSettings.gamepadReverseAxis, controlSettings.gamepadReverseSign, controlSettings.gamepadSteeringInvert, controlSettings.gamepadThrottleInvert, controlSettings.gamepadReverseInvert) {
        val activity = context as? MainActivity
        if (isGamepadMode && isLandscape) {
            val selectedDeviceId = if (controlSettings.gamepadDeviceName.isNotEmpty()) {
                InputDevice.getDeviceIds()
                    .toList()
                    .mapNotNull { InputDevice.getDevice(it) }
                    .firstOrNull { it.name == controlSettings.gamepadDeviceName }
                    ?.id
            } else {
                null
            }

            val controller = GamepadController(
                controlState = controlState,
                deviceId = selectedDeviceId,
                steeringAxis = controlSettings.gamepadSteeringAxis,
                steeringSign = controlSettings.gamepadSteeringSign,
                throttleAxis = controlSettings.gamepadThrottleAxis,
                throttleSign = controlSettings.gamepadThrottleSign,
                reverseAxis = controlSettings.gamepadReverseAxis,
                reverseSign = controlSettings.gamepadReverseSign,
                steeringInvert = controlSettings.gamepadSteeringInvert,
                throttleInvert = controlSettings.gamepadThrottleInvert,
                reverseInvert = controlSettings.gamepadReverseInvert
            )
            activity?.onGamepadMotionEvent = { controller.handleMotionEvent(it) }
        }
        onDispose {
            activity?.onGamepadMotionEvent = null
            controlState.reset()
        }
    }

    // Reset controls when switching to portrait mode
    if (!isLandscape) {
        controlState.reset()
    }

    // Poll control channel timeout
    LaunchedEffect(Unit) {
        while (true) {
            delay(1000)
            viewerState.checkControlTimeout()
        }
    }

    // Show toast when GStreamer pipeline restarts after error/EOS
    LaunchedEffect(Unit) {
        var lastCount = GstViewer.restartCount
        while (true) {
            delay(2000)
            val count = GstViewer.restartCount
            if (count > lastCount) {
                lastCount = count
                Toast.makeText(context, R.string.pipeline_restarted, Toast.LENGTH_SHORT).show()
            }
        }
    }

    // Video blank timeout - blank video after 5 seconds of video service stopped
    LaunchedEffect(viewerState.isVideoRunning) {
        if (!viewerState.isVideoRunning) {
            delay(5000)
            showVideoBlank = true
        } else {
            showVideoBlank = false
        }
    }

    // Handle fullscreen mode and keep screen on
    DisposableEffect(isLandscape) {
        val activity = context as? Activity
        val window = activity?.window
        val insetsController = if (window != null) {
            WindowCompat.getInsetsController(window, window.decorView)
        } else null

        if (isLandscape && insetsController != null) {
            insetsController.hide(WindowInsetsCompat.Type.systemBars())
            insetsController.systemBarsBehavior =
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        } else if (insetsController != null) {
            insetsController.show(WindowInsetsCompat.Type.systemBars())
        }

        onDispose {
            insetsController?.show(WindowInsetsCompat.Type.systemBars())
        }
    }

    // Allow rotation, keep screen on, and request max refresh rate while viewing video
    DisposableEffect(Unit) {
        val activity = context as? Activity
        activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR
        activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val display = activity?.display ?: @Suppress("DEPRECATION") activity?.windowManager?.defaultDisplay
        val maxRefreshRate = display?.supportedModes
            ?.maxOfOrNull { it.refreshRate } ?: 0f
        if (maxRefreshRate > 0f) {
            activity?.window?.attributes = activity.window.attributes.apply {
                preferredRefreshRate = maxRefreshRate
            }
        }

        onDispose {
            activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
            activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            activity?.window?.attributes = activity.window.attributes.apply {
                preferredRefreshRate = 0f
            }
        }
    }

    // WiFi low-latency lock to prevent network throttling during streaming
    DisposableEffect(Unit) {
        val wifiManager = context.applicationContext
            .getSystemService(Context.WIFI_SERVICE) as? WifiManager
        val wifiLock = wifiManager?.createWifiLock(
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                WifiManager.WIFI_MODE_FULL_LOW_LATENCY
            } else {
                @Suppress("DEPRECATION")
                WifiManager.WIFI_MODE_FULL_HIGH_PERF
            },
            "v3xctrl:viewer"
        )
        wifiLock?.acquire()

        onDispose {
            if (wifiLock?.isHeld == true) {
                wifiLock.release()
            }
        }
    }

    DisposableEffect(Unit) {
        GstViewer.init()
        onDispose {
            GstViewer.stop()
            isPipelineStarted = false
        }
    }

    // Video port keep-alive: send Heartbeat to relay to maintain NAT hole.
    // Only needed in UDP mode, TCP maintains the connection.
    if (connection.transport == Transport.UDP) {
        LaunchedEffect(connection.videoPort, connection.relayHost, connection.relayPort) {
            withContext(Dispatchers.IO) {
                val relayAddress = try {
                    InetAddress.getByName(connection.relayHost)
                } catch (e: Exception) {
                    return@withContext
                }

                val keepAlive = VideoPortKeepAlive(
                    videoPort = connection.videoPort,
                    relayAddress = relayAddress,
                    relayPort = connection.relayPort
                )

                var keepAliveSocket: DatagramSocket? = null
                try {
                    keepAliveSocket = keepAlive.createSocket()

                    while (true) {
                        try {
                            keepAlive.sendHeartbeat(keepAliveSocket)
                        } catch (_: Exception) {
                            // Ignore send errors
                        }
                        delay(keepAlive.getIntervalMs(viewerState.isVideoRunning))
                    }
                } catch (_: Exception) {
                    // Socket bind may fail if SO_REUSEADDR isn't supported
                } finally {
                    keepAliveSocket?.close()
                }
            }
        }
    }

    // Start control channel receiver
    DisposableEffect(connection.controlPort, connection.relayHost, connection.relayPort, connection.sessionId, controlHz, spectatorMode, controlSettings.forwardScale, controlSettings.backwardScale, controlSettings.steeringScale, connection.transport) {
        val receiver = UDPReceiver(
            port = connection.controlPort,
            relayHost = connection.relayHost,
            relayPort = connection.relayPort,
            sessionId = connection.sessionId,
            scope = scope,
            controlHz = controlHz,
            controlState = controlState,
            viewerState = viewerState,
            spectatorMode = spectatorMode,
            forwardScale = controlSettings.forwardScale / 100f,
            backwardScale = controlSettings.backwardScale / 100f,
            steeringScale = controlSettings.steeringScale / 100f,
            transport = connection.transport
        )
        receiver.start()
        udpReceiver = receiver
        onDispose {
            receiver.stop()
            udpReceiver = null
        }
    }

    // Remember the SurfaceView to persist it across recompositions
    val surfaceView = remember(connection.videoPort) {
        SurfaceView(context).apply {
            isFocusable = false
            isFocusableInTouchMode = false
            holder.addCallback(object : SurfaceHolder.Callback {
                override fun surfaceCreated(holder: SurfaceHolder) {
                    if (!isPipelineStarted) {
                        GstViewer.start(holder.surface, connection.videoPort)
                        isPipelineStarted = true
                    } else {
                        GstViewer.resume(holder.surface)
                    }
                }

                override fun surfaceChanged(
                    holder: SurfaceHolder,
                    format: Int,
                    width: Int,
                    height: Int
                ) {
                    // Surface resized - pipeline handles this automatically
                }

                override fun surfaceDestroyed(holder: SurfaceHolder) {
                    GstViewer.pause()
                }
            })
        }
    }

    if (isInPipMode) {
        // PiP: show only video, no controls or OSD
        VideoSurface(
            surfaceView = surfaceView,
            showVideoBlank = showVideoBlank,
            modifier = Modifier.fillMaxSize()
        )
    } else if (isLandscape) {
        LandscapeViewer(
            surfaceView = surfaceView,
            showVideoBlank = showVideoBlank,
            controlState = controlState,
            viewerState = viewerState,
            motionController = motionController,
            isMotionMode = isMotionMode,
            isGamepadMode = isGamepadMode,
            spectatorMode = spectatorMode,
            pipelineStartTime = pipelineStartTime,
            osdSettings = osdSettings,
            fps = fps,
            touchSteeringInvert = controlSettings.touchSteeringInvert,
            touchThrottleInvert = controlSettings.touchThrottleInvert,
            modifier = modifier
        )
    } else {
        PortraitViewer(
            surfaceView = surfaceView,
            showVideoBlank = showVideoBlank,
            viewerState = viewerState,
            udpReceiver = udpReceiver,
            spectatorMode = spectatorMode,
            osdSettings = osdSettings,
            fps = fps,
            showPipelineStats = showPipelineStats,
            onBack = {
                GstViewer.stop()
                isPipelineStarted = false
                onBack()
            },
            onNavigateToGeneral = onNavigateToGeneral,
            onNavigateToNetwork = onNavigateToNetwork,
            onNavigateToFrequencies = onNavigateToFrequencies,
            onNavigateToOSD = onNavigateToOSD,
            onNavigateToControl = onNavigateToControl,
            modifier = modifier
        )
    }
}

@Composable
fun VideoSurface(
    surfaceView: SurfaceView,
    showVideoBlank: Boolean,
    modifier: Modifier = Modifier
) {
    AndroidView(
        factory = { surfaceView },
        modifier = modifier
    )

    if (showVideoBlank) {
        Box(modifier = modifier.background(Color.Black))
    }
}
