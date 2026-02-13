package com.v3xctrl.viewer.ui.screens

import android.app.Activity
import android.content.pm.ActivityInfo
import android.content.res.Configuration
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
import com.v3xctrl.viewer.input.GamepadController
import com.v3xctrl.viewer.input.MotionController
import com.v3xctrl.viewer.control.UDPReceiver
import com.v3xctrl.viewer.control.ViewerState
import com.v3xctrl.viewer.messages.Heartbeat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress

data class ConnectionInfo(
    val videoPort: Int,
    val controlPort: Int,
    val relayHost: String,
    val relayPort: Int,
    val sessionId: String
)

@Composable
fun ViewerScreen(
    connection: ConnectionInfo,
    controlHz: Int = 30,
    showPipelineTimer: Boolean = false,
    spectatorMode: Boolean = false,
    controlSettings: ControlSettings = ControlSettings(),
    onBack: () -> Unit,
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

    // Pipeline start time for timer widget
    val pipelineStartTime = remember { System.currentTimeMillis() }

    // Motion controller for gyroscope-based control
    val isMotionMode = controlSettings.controlMode == "motion" && !spectatorMode
    var motionController by remember { mutableStateOf<MotionController?>(null) }

    // Gamepad controller for USB/Bluetooth HID controllers
    val isGamepadMode = controlSettings.controlMode == "gamepad" && !spectatorMode

    // Start/stop motion controller based on mode and orientation
    DisposableEffect(isMotionMode, isLandscape, controlSettings.motionSteeringDeg, controlSettings.motionForwardDeg, controlSettings.motionBackwardDeg) {
        if (isMotionMode && isLandscape) {
            val controller = MotionController(
                context = context,
                controlState = controlState,
                steeringDeg = controlSettings.motionSteeringDeg.toFloat(),
                forwardDeg = controlSettings.motionForwardDeg.toFloat(),
                backwardDeg = controlSettings.motionBackwardDeg.toFloat()
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
    DisposableEffect(isGamepadMode, isLandscape, controlSettings.gamepadDeviceName, controlSettings.gamepadSteeringAxis, controlSettings.gamepadSteeringSign, controlSettings.gamepadThrottleAxis, controlSettings.gamepadThrottleSign, controlSettings.gamepadReverseAxis, controlSettings.gamepadReverseSign) {
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
                reverseSign = controlSettings.gamepadReverseSign
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

    // Connection timeout check
    LaunchedEffect(Unit) {
        while (true) {
            delay(1000)
            if (viewerState.isConnectionTimedOut()) {
                // Connection lost - return to main screen
                GstViewer.stop()
                onBack()
                break
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

    // Allow rotation and keep screen on while viewing video
    DisposableEffect(Unit) {
        val activity = context as? Activity
        activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR
        activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        onDispose {
            activity?.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
            activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    DisposableEffect(Unit) {
        GstViewer.init()
        onDispose {
            GstViewer.stop()
        }
    }

    // Video port keep-alive: send Heartbeat to relay to maintain NAT hole
    // when video service is not running, so the relay can forward video once started
    LaunchedEffect(connection.videoPort, connection.relayHost, connection.relayPort) {
        withContext(Dispatchers.IO) {
            val relayAddress = try {
                InetAddress.getByName(connection.relayHost)
            } catch (e: Exception) {
                return@withContext
            }

            var keepAliveSocket: DatagramSocket? = null
            try {
                keepAliveSocket = DatagramSocket(null).apply {
                    reuseAddress = true
                    bind(InetSocketAddress(connection.videoPort))
                }

                while (true) {
                    if (!viewerState.isVideoRunning) {
                        try {
                            val data = Heartbeat().toBytes()
                            val packet = DatagramPacket(data, data.size, relayAddress, connection.relayPort)
                            keepAliveSocket.send(packet)
                        } catch (_: Exception) {
                            // Ignore send errors
                        }
                    }
                    delay(1000)
                }
            } catch (_: Exception) {
                // Socket bind may fail if SO_REUSEADDR isn't supported
            } finally {
                keepAliveSocket?.close()
            }
        }
    }

    // Start control channel receiver
    DisposableEffect(connection.controlPort, connection.relayHost, connection.relayPort, connection.sessionId, controlHz, spectatorMode, controlSettings.forwardScale, controlSettings.backwardScale, controlSettings.steeringScale) {
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
            steeringScale = controlSettings.steeringScale / 100f
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
                    GstViewer.start(holder.surface, connection.videoPort)
                }

                override fun surfaceChanged(
                    holder: SurfaceHolder,
                    format: Int,
                    width: Int,
                    height: Int
                ) {
                    // Handle surface changes if needed
                }

                override fun surfaceDestroyed(holder: SurfaceHolder) {
                    GstViewer.stop()
                }
            })
        }
    }

    if (isLandscape) {
        LandscapeViewer(
            surfaceView = surfaceView,
            showVideoBlank = showVideoBlank,
            controlState = controlState,
            viewerState = viewerState,
            motionController = motionController,
            isMotionMode = isMotionMode,
            isGamepadMode = isGamepadMode,
            spectatorMode = spectatorMode,
            showPipelineTimer = showPipelineTimer,
            pipelineStartTime = pipelineStartTime,
            modifier = modifier
        )
    } else {
        PortraitViewer(
            surfaceView = surfaceView,
            showVideoBlank = showVideoBlank,
            viewerState = viewerState,
            udpReceiver = udpReceiver,
            spectatorMode = spectatorMode,
            onBack = {
                GstViewer.stop()
                onBack()
            },
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
        Box(
            modifier = modifier
                .background(Color.Black)
        )
    }
}
