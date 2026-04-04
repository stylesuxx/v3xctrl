package com.v3xctrl.viewer

import android.app.PictureInPictureParams
import android.view.MotionEvent
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.os.Build
import android.os.Bundle
import android.util.Rational
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.foundation.layout.Box
import androidx.compose.ui.platform.LocalContext
import com.v3xctrl.viewer.data.ControlSettings
import com.v3xctrl.viewer.data.FrequencySettings
import com.v3xctrl.viewer.data.GeneralSettings
import com.v3xctrl.viewer.data.NetworkSettings
import com.v3xctrl.viewer.data.OsdSettings
import com.v3xctrl.viewer.data.SettingsDataStore
import com.v3xctrl.viewer.data.Transport
import com.v3xctrl.viewer.messages.PeerAnnouncement
import com.v3xctrl.viewer.messages.PortType
import com.v3xctrl.viewer.messages.Role
import com.v3xctrl.viewer.network.tcp.TcpTunnel
import com.v3xctrl.viewer.relay.ConnectionResult
import com.v3xctrl.viewer.relay.RelayConnection
import com.v3xctrl.viewer.ui.screens.ControlScreen
import com.v3xctrl.viewer.ui.screens.FrequenciesScreen
import com.v3xctrl.viewer.ui.screens.GeneralScreen
import com.v3xctrl.viewer.ui.screens.MainScreen
import com.v3xctrl.viewer.ui.screens.NetworkScreen
import com.v3xctrl.viewer.ui.screens.OSDScreen
import com.v3xctrl.viewer.ui.screens.ConnectionInfo
import com.v3xctrl.viewer.ui.screens.ViewerScreen
import com.v3xctrl.viewer.ui.theme.V3xctrlTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.DatagramSocket

sealed class ConnectionState {
    object Idle : ConnectionState()
    object Connecting : ConnectionState()
    data class Error(val message: String) : ConnectionState()
}

enum class Screen {
    Main,
    General,
    Network,
    Frequencies,
    OSD,
    Control,
    Viewer
}

private fun parseRelayUrl(url: String): Pair<String, Int> {
    val parts = url.split(":")
    val host = parts.getOrElse(0) { "localhost" }
    val port = parts.getOrElse(1) { "8888" }.toIntOrNull() ?: 8888
    return Pair(host, port)
}

class MainActivity : ComponentActivity() {
    var onGamepadMotionEvent: ((MotionEvent) -> Boolean)? = null
    var currentScreen by mutableStateOf(Screen.Main)
    var isInPipMode by mutableStateOf(false)

    override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean {
        onGamepadMotionEvent?.let { handler ->
            if (handler(event)) return true
        }
        return super.dispatchGenericMotionEvent(event)
    }

    override fun onUserLeaveHint() {
        super.onUserLeaveHint()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            && currentScreen == Screen.Viewer) {
            enterPictureInPictureMode(
                PictureInPictureParams.Builder()
                    .setAspectRatio(Rational(16, 9))
                    .build()
            )
        }
    }

    override fun onPictureInPictureModeChanged(
        inPipMode: Boolean,
        newConfig: Configuration
    ) {
        super.onPictureInPictureModeChanged(inPipMode, newConfig)
        isInPipMode = inPipMode
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // Force dark mode at the configuration level before anything renders,
        // so Compose and system UI both start in dark mode on all devices
        val config = resources.configuration
        val currentNightMode = config.uiMode and Configuration.UI_MODE_NIGHT_MASK
        if (currentNightMode != Configuration.UI_MODE_NIGHT_YES) {
            config.uiMode = (config.uiMode and Configuration.UI_MODE_NIGHT_MASK.inv()) or
                Configuration.UI_MODE_NIGHT_YES
            @Suppress("DEPRECATION")
            resources.updateConfiguration(config, resources.displayMetrics)
        }
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT)
        )
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        setContent {
            V3xctrlTheme {
                val context = LocalContext.current
                val settingsDataStore = remember { SettingsDataStore(context) }
                val generalSettings by settingsDataStore.generalSettings.collectAsState(
                    initial = GeneralSettings()
                )
                val networkSettings by settingsDataStore.networkSettings.collectAsState(
                    initial = NetworkSettings()
                )
                val frequencySettings by settingsDataStore.frequencySettings.collectAsState(
                    initial = FrequencySettings()
                )
                val osdSettings by settingsDataStore.osdSettings.collectAsState(
                    initial = OsdSettings()
                )
                val controlSettings by settingsDataStore.controlSettings.collectAsState(
                    initial = ControlSettings()
                )
                val pipelineStatsActive = generalSettings.enableDebugStats && generalSettings.showPipelineStats
                LaunchedEffect(pipelineStatsActive) {
                    GstViewer.setStatsEnabled(pipelineStatsActive)
                }

                val scope = rememberCoroutineScope()

                val backStack = remember { mutableStateListOf<Screen>() }

                fun navigateTo(screen: Screen) {
                    backStack.add(currentScreen)
                    currentScreen = screen
                }

                // Auto-enter PiP on gesture navigation (API 31+)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    LaunchedEffect(currentScreen) {
                        setPictureInPictureParams(
                            PictureInPictureParams.Builder()
                                .setAspectRatio(Rational(16, 9))
                                .setAutoEnterEnabled(currentScreen == Screen.Viewer)
                                .build()
                        )
                    }
                }

                var connectionState by remember { mutableStateOf<ConnectionState>(ConnectionState.Idle) }
                var connectionJob by remember { mutableStateOf<Job?>(null) }
                var relayConnection by remember { mutableStateOf<RelayConnection?>(null) }

                // Dynamic ports assigned during relay handshake
                var dynamicVideoPort by remember { mutableStateOf(0) }
                var dynamicControlPort by remember { mutableStateOf(0) }

                // TCP tunnels (only used when transport == "tcp")
                var videoTunnel by remember { mutableStateOf<TcpTunnel?>(null) }
                var controlTunnel by remember { mutableStateOf<TcpTunnel?>(null) }

                // Track the network settings used for the active connection,
                // so we can detect changes that require reconnection
                var connectionNetworkSettings by remember { mutableStateOf<NetworkSettings?>(null) }
                var isReconnecting by remember { mutableStateOf(false) }
                var reconnectionGeneration by remember { mutableIntStateOf(0) }

                fun stopTunnels() {
                    videoTunnel?.stop()
                    controlTunnel?.stop()
                    videoTunnel = null
                    controlTunnel = null
                }

                fun startConnection() {
                    val (host, port) = parseRelayUrl(networkSettings.relayUrl)
                    val transport = networkSettings.transport
                    connectionState = ConnectionState.Connecting

                    if (transport == Transport.TCP) {
                        // TCP relay mode: skip RelayConnection, use TcpTunnels
                        connectionJob = scope.launch {
                            val startTime = System.currentTimeMillis()

                            try {
                                // Allocate two ephemeral ports
                                val (vPort, cPort) = withContext(Dispatchers.IO) {
                                    val vs = DatagramSocket(0)
                                    val cs = DatagramSocket(0)
                                    val vp = vs.localPort
                                    val cp = cs.localPort
                                    vs.close()
                                    cs.close()
                                    Pair(vp, cp)
                                }

                                val role = if (networkSettings.spectatorMode) Role.SPECTATOR else Role.VIEWER

                                val vTunnel = TcpTunnel(
                                    remoteHost = host,
                                    remotePort = port,
                                    localComponentPort = vPort,
                                    bidirectional = true,
                                    handshake = PeerAnnouncement(
                                        role = role,
                                        sessionId = networkSettings.sessionId,
                                        portType = PortType.VIDEO
                                    ).toBytes()
                                )

                                val cTunnel = TcpTunnel(
                                    remoteHost = host,
                                    remotePort = port,
                                    localComponentPort = cPort,
                                    bidirectional = true,
                                    handshake = PeerAnnouncement(
                                        role = role,
                                        sessionId = networkSettings.sessionId,
                                        portType = PortType.CONTROL
                                    ).toBytes()
                                )

                                vTunnel.start()
                                cTunnel.start()

                                videoTunnel = vTunnel
                                controlTunnel = cTunnel
                                dynamicVideoPort = vPort
                                dynamicControlPort = cPort
                                connectionNetworkSettings = networkSettings

                                // Show connecting state for at least 1.5 seconds
                                val elapsed = System.currentTimeMillis() - startTime
                                if (elapsed < 1500) delay(1500 - elapsed)

                                connectionState = ConnectionState.Idle
                                navigateTo(Screen.Viewer)
                            } catch (e: Exception) {
                                val elapsed = System.currentTimeMillis() - startTime
                                if (elapsed < 1500) delay(1500 - elapsed)
                                stopTunnels()
                                connectionState = ConnectionState.Error(
                                    e.message ?: "TCP connection failed"
                                )
                            }
                        }
                    } else {
                        val connection = RelayConnection(
                            relayHost = host,
                            relayPort = port,
                            sessionId = networkSettings.sessionId,
                            spectatorMode = networkSettings.spectatorMode
                        )
                        relayConnection = connection

                        connectionJob = scope.launch {
                            val startTime = System.currentTimeMillis()
                            val result = connection.connect()
                            // Show connecting state for at least 1.5 seconds
                            val elapsed = System.currentTimeMillis() - startTime
                            if (elapsed < 1500) delay(1500 - elapsed)
                            when (result) {
                                is ConnectionResult.Success -> {
                                    dynamicVideoPort = result.videoPort
                                    dynamicControlPort = result.controlPort
                                    connectionNetworkSettings = networkSettings
                                    connectionState = ConnectionState.Idle
                                    navigateTo(Screen.Viewer)
                                }
                                is ConnectionResult.Unauthorized -> {
                                    connectionState = ConnectionState.Error(result.message)
                                }
                                is ConnectionResult.Error -> {
                                    connectionState = ConnectionState.Error(result.message)
                                }
                                is ConnectionResult.Cancelled -> {
                                    connectionState = ConnectionState.Idle
                                }
                            }
                            relayConnection = null
                        }
                    }
                }

                fun abortConnection() {
                    relayConnection?.cancel()
                    connectionJob?.cancel()
                    stopTunnels()
                    connectionState = ConnectionState.Idle
                    relayConnection = null
                    connectionJob = null
                }

                fun reconnect() {
                    connectionJob?.cancel()
                    relayConnection?.cancel()
                    relayConnection = null
                    isReconnecting = true

                    val (host, port) = parseRelayUrl(networkSettings.relayUrl)
                    val transport = networkSettings.transport

                    fun onReconnectFailed(message: String) {
                        isReconnecting = false
                        connectionNetworkSettings = null
                        connectionState = ConnectionState.Error(message)
                        backStack.clear()
                        currentScreen = Screen.Main
                    }

                    if (transport == Transport.TCP) {
                        connectionJob = scope.launch {
                            try {
                                stopTunnels()

                                val (vPort, cPort) = withContext(Dispatchers.IO) {
                                    val vs = DatagramSocket(0)
                                    val cs = DatagramSocket(0)
                                    val vp = vs.localPort
                                    val cp = cs.localPort
                                    vs.close()
                                    cs.close()
                                    Pair(vp, cp)
                                }

                                val role = if (networkSettings.spectatorMode) Role.SPECTATOR else Role.VIEWER

                                val vTunnel = TcpTunnel(
                                    remoteHost = host,
                                    remotePort = port,
                                    localComponentPort = vPort,
                                    bidirectional = true,
                                    handshake = PeerAnnouncement(
                                        role = role,
                                        sessionId = networkSettings.sessionId,
                                        portType = PortType.VIDEO
                                    ).toBytes()
                                )

                                val cTunnel = TcpTunnel(
                                    remoteHost = host,
                                    remotePort = port,
                                    localComponentPort = cPort,
                                    bidirectional = true,
                                    handshake = PeerAnnouncement(
                                        role = role,
                                        sessionId = networkSettings.sessionId,
                                        portType = PortType.CONTROL
                                    ).toBytes()
                                )

                                vTunnel.start()
                                cTunnel.start()

                                videoTunnel = vTunnel
                                controlTunnel = cTunnel
                                dynamicVideoPort = vPort
                                dynamicControlPort = cPort
                                connectionNetworkSettings = networkSettings
                                reconnectionGeneration++
                                isReconnecting = false
                            } catch (e: Exception) {
                                stopTunnels()
                                onReconnectFailed(e.message ?: "Reconnection failed")
                            }
                        }
                    } else {
                        connectionJob = scope.launch {
                            stopTunnels()

                            val connection = RelayConnection(
                                relayHost = host,
                                relayPort = port,
                                sessionId = networkSettings.sessionId,
                                spectatorMode = networkSettings.spectatorMode
                            )
                            relayConnection = connection

                            val result = connection.connect()
                            relayConnection = null

                            when (result) {
                                is ConnectionResult.Success -> {
                                    dynamicVideoPort = result.videoPort
                                    dynamicControlPort = result.controlPort
                                    connectionNetworkSettings = networkSettings
                                    reconnectionGeneration++
                                    isReconnecting = false
                                }
                                is ConnectionResult.Cancelled -> {
                                    isReconnecting = false
                                }
                                is ConnectionResult.Unauthorized -> {
                                    onReconnectFailed(result.message)
                                }
                                is ConnectionResult.Error -> {
                                    onReconnectFailed(result.message)
                                }
                            }
                        }
                    }
                }

                fun navigateBack() {
                    currentScreen = backStack.removeLastOrNull() ?: Screen.Main

                    // If returning to the viewer and connection-affecting settings
                    // changed, reconnect in place
                    if (currentScreen == Screen.Viewer
                        && connectionNetworkSettings != null
                        && networkSettings != connectionNetworkSettings
                    ) {
                        reconnect()
                    }
                }

                BackHandler(enabled = currentScreen != Screen.Main) {
                    navigateBack()
                }

                Box {
                    // Keep ViewerScreen alive when navigating to settings,
                    // preserving pipeline, control connection, and button state
                    if (currentScreen == Screen.Viewer || backStack.contains(Screen.Viewer)) {
                        val (relayHost, relayPort) = parseRelayUrl(networkSettings.relayUrl)
                        ViewerScreen(
                            connection = ConnectionInfo(
                                videoPort = dynamicVideoPort,
                                controlPort = dynamicControlPort,
                                relayHost = relayHost,
                                relayPort = relayPort,
                                sessionId = networkSettings.sessionId,
                                transport = networkSettings.transport
                            ),
                            controlHz = frequencySettings.controlHz,
                            controlBufferCapacity = frequencySettings.controlBufferCapacity,
                            renderQueueSize = frequencySettings.renderQueueSize,
                            osdSettings = osdSettings,
                            generalSettings = generalSettings,
                            spectatorMode = networkSettings.spectatorMode,
                            controlSettings = controlSettings,
                            isInPipMode = isInPipMode,
                            isReconnecting = isReconnecting,
                            reconnectionGeneration = reconnectionGeneration,
                            onBack = {
                                stopTunnels()
                                navigateBack()
                            },
                            onNavigateToGeneral = { navigateTo(Screen.General) },
                            onNavigateToNetwork = { navigateTo(Screen.Network) },
                            onNavigateToFrequencies = { navigateTo(Screen.Frequencies) },
                            onNavigateToOSD = { navigateTo(Screen.OSD) },
                            onNavigateToControl = { navigateTo(Screen.Control) }
                        )
                    }

                    when (currentScreen) {
                        Screen.Viewer -> { /* rendered above */ }
                        Screen.Main -> MainScreen(
                            relayUrl = networkSettings.relayUrl,
                            sessionId = networkSettings.sessionId,
                            connectionState = connectionState,
                            onStartConnection = { startConnection() },
                            onAbortConnection = { abortConnection() },
                            onClearError = { connectionState = ConnectionState.Idle },
                            onNavigateToGeneral = { navigateTo(Screen.General) },
                            onNavigateToNetwork = { navigateTo(Screen.Network) },
                            onNavigateToFrequencies = { navigateTo(Screen.Frequencies) },
                            onNavigateToOSD = { navigateTo(Screen.OSD) },
                            onNavigateToControl = { navigateTo(Screen.Control) }
                        )
                        Screen.General -> GeneralScreen(
                            settings = generalSettings,
                            onSettingsChange = { scope.launch { settingsDataStore.updateGeneralSettings(it) } },
                            onBack = { navigateBack() }
                        )
                        Screen.Network -> NetworkScreen(
                            settings = networkSettings,
                            onSettingsChange = { scope.launch { settingsDataStore.updateNetworkSettings(it) } },
                            onBack = { navigateBack() }
                        )
                        Screen.Frequencies -> FrequenciesScreen(
                            settings = frequencySettings,
                            onSettingsChange = { scope.launch { settingsDataStore.updateFrequencySettings(it) } },
                            onBack = { navigateBack() }
                        )
                        Screen.OSD -> OSDScreen(
                            settings = osdSettings,
                            onSettingsChange = { scope.launch { settingsDataStore.updateOsdSettings(it) } },
                            onBack = { navigateBack() }
                        )
                        Screen.Control -> ControlScreen(
                            settings = controlSettings,
                            onSettingsChange = { scope.launch { settingsDataStore.updateControlSettings(it) } },
                            onBack = { navigateBack() }
                        )
                    }
                }
            }
        }
    }
}
