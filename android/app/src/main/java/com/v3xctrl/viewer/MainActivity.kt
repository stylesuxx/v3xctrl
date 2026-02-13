package com.v3xctrl.viewer

import android.view.MotionEvent
import android.content.pm.ActivityInfo
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.v3xctrl.viewer.data.ControlSettings
import com.v3xctrl.viewer.data.FrequencySettings
import com.v3xctrl.viewer.data.NetworkSettings
import com.v3xctrl.viewer.data.OsdSettings
import com.v3xctrl.viewer.data.SettingsDataStore
import com.v3xctrl.viewer.relay.ConnectionResult
import com.v3xctrl.viewer.relay.RelayConnection
import com.v3xctrl.viewer.ui.screens.ControlScreen
import com.v3xctrl.viewer.ui.screens.FrequenciesScreen
import com.v3xctrl.viewer.ui.screens.MainScreen
import com.v3xctrl.viewer.ui.screens.NetworkScreen
import com.v3xctrl.viewer.ui.screens.OSDScreen
import com.v3xctrl.viewer.ui.screens.ConnectionInfo
import com.v3xctrl.viewer.ui.screens.ViewerScreen
import com.v3xctrl.viewer.ui.theme.V3xctrlTheme
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

sealed class ConnectionState {
    object Idle : ConnectionState()
    object Connecting : ConnectionState()
    data class Error(val message: String) : ConnectionState()
}

enum class Screen {
    Main,
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

    override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean {
        onGamepadMotionEvent?.let { handler ->
            if (handler(event)) return true
        }
        return super.dispatchGenericMotionEvent(event)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        setContent {
            V3xctrlTheme {
                val context = LocalContext.current
                val settingsDataStore = remember { SettingsDataStore(context) }
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
                val scope = rememberCoroutineScope()

                var currentScreen by remember { mutableStateOf(Screen.Main) }
                val backStack = remember { mutableStateListOf<Screen>() }

                fun navigateTo(screen: Screen) {
                    backStack.add(currentScreen)
                    currentScreen = screen
                }

                fun navigateBack() {
                    currentScreen = backStack.removeLastOrNull() ?: Screen.Main
                }

                var connectionState by remember { mutableStateOf<ConnectionState>(ConnectionState.Idle) }
                var connectionJob by remember { mutableStateOf<Job?>(null) }
                var relayConnection by remember { mutableStateOf<RelayConnection?>(null) }

                // Dynamic ports assigned during relay handshake
                var dynamicVideoPort by remember { mutableStateOf(0) }
                var dynamicControlPort by remember { mutableStateOf(0) }

                fun startConnection() {
                    val (host, port) = parseRelayUrl(networkSettings.relayUrl)
                    connectionState = ConnectionState.Connecting

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

                fun abortConnection() {
                    relayConnection?.cancel()
                    connectionJob?.cancel()
                    connectionState = ConnectionState.Idle
                    relayConnection = null
                    connectionJob = null
                }

                BackHandler(enabled = currentScreen != Screen.Main) {
                    navigateBack()
                }

                when (currentScreen) {
                    Screen.Main -> MainScreen(
                        relayUrl = networkSettings.relayUrl,
                        sessionId = networkSettings.sessionId,
                        connectionState = connectionState,
                        onStartConnection = { startConnection() },
                        onAbortConnection = { abortConnection() },
                        onClearError = { connectionState = ConnectionState.Idle },
                        onNavigateToNetwork = { navigateTo(Screen.Network) },
                        onNavigateToFrequencies = { navigateTo(Screen.Frequencies) },
                        onNavigateToOSD = { navigateTo(Screen.OSD) },
                        onNavigateToControl = { navigateTo(Screen.Control) }
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
                    Screen.Viewer -> {
                        val (relayHost, relayPort) = parseRelayUrl(networkSettings.relayUrl)
                        ViewerScreen(
                            connection = ConnectionInfo(
                                videoPort = dynamicVideoPort,
                                controlPort = dynamicControlPort,
                                relayHost = relayHost,
                                relayPort = relayPort,
                                sessionId = networkSettings.sessionId
                            ),
                            controlHz = frequencySettings.controlHz,
                            showPipelineTimer = osdSettings.showPipelineTimer,
                            spectatorMode = networkSettings.spectatorMode,
                            controlSettings = controlSettings,
                            onBack = { navigateBack() },
                            onNavigateToNetwork = { navigateTo(Screen.Network) },
                            onNavigateToFrequencies = { navigateTo(Screen.Frequencies) },
                            onNavigateToOSD = { navigateTo(Screen.OSD) },
                            onNavigateToControl = { navigateTo(Screen.Control) }
                        )
                    }
                }
            }
        }
    }
}
