package com.v3xctrl.viewer.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

enum class Transport {
    UDP, TCP;

    companion object {
        fun fromString(value: String): Transport {
            return when (value.lowercase()) {
                "tcp" -> TCP
                else -> UDP
            }
        }
    }
}

data class GeneralSettings(
    val enableDebugStats: Boolean = false,
    val showPipelineStats: Boolean = true,
    val showSystemStats: Boolean = true
)

data class NetworkSettings(
    val relayUrl: String = "relay.v3xctrl.com:8888",
    val sessionId: String = "",
    val spectatorMode: Boolean = false,
    val transport: Transport = Transport.UDP
)

data class FrequencySettings(
    val controlHz: Int = 30,
    val controlBufferCapacity: Int = 1,
    val renderQueueSize: Int = 1
)

data class OsdSettings(
    val showPipelineTimer: Boolean = false,
    val showBattery: Boolean = true,
    val showBatteryIcon: Boolean = true,
    val showBatteryVoltage: Boolean = true,
    val showBatteryCellVoltage: Boolean = true,
    val showBatteryPercent: Boolean = true,
    val showBatteryCurrent: Boolean = true,
    val showSignal: Boolean = true,
    val showSignalIcon: Boolean = true,
    val showSignalBand: Boolean = false,
    val showSignalCellId: Boolean = false,
    val showFrameDrops: Boolean = true,
    val showFps: Boolean = false
)

data class ControlSettings(
    val controlMode: String = "touch",
    val forwardScale: Int = 100,
    val backwardScale: Int = 100,
    val steeringScale: Int = 100,
    val motionSteeringDeg: Int = 45,
    val motionForwardDeg: Int = 45,
    val motionBackwardDeg: Int = 45,
    val gamepadDeviceName: String = "",
    val gamepadSteeringAxis: Int = 0,
    val gamepadSteeringSign: Int = 1,
    val gamepadThrottleAxis: Int = 1,
    val gamepadThrottleSign: Int = -1,
    val gamepadReverseAxis: Int = 1,
    val gamepadReverseSign: Int = 1,
    val gamepadSteeringInvert: Boolean = false,
    val gamepadThrottleInvert: Boolean = false,
    val gamepadReverseInvert: Boolean = false,
    val touchSteeringInvert: Boolean = false,
    val touchThrottleInvert: Boolean = false,
    val motionSteeringInvert: Boolean = false,
    val motionThrottleInvert: Boolean = false
)

class SettingsDataStore(private val context: Context) {

    companion object {
        private val ENABLE_DEBUG_STATS = booleanPreferencesKey("enable_debug_stats")
        private val SHOW_PIPELINE_STATS = booleanPreferencesKey("show_pipeline_stats")
        private val SHOW_SYSTEM_STATS = booleanPreferencesKey("show_system_stats")

        private val RELAY_URL = stringPreferencesKey("relay_url")
        private val SESSION_ID = stringPreferencesKey("session_id")
        private val SPECTATOR_MODE = booleanPreferencesKey("spectator_mode")
        private val TRANSPORT = stringPreferencesKey("transport")

        private val SHOW_PIPELINE_TIMER = booleanPreferencesKey("show_pipeline_timer")

        private val SHOW_BATTERY = booleanPreferencesKey("show_battery")
        private val SHOW_BATTERY_ICON = booleanPreferencesKey("show_battery_icon")
        private val SHOW_BATTERY_VOLTAGE = booleanPreferencesKey("show_battery_voltage")
        private val SHOW_BATTERY_CELL_VOLTAGE = booleanPreferencesKey("show_battery_cell_voltage")
        private val SHOW_BATTERY_PERCENT = booleanPreferencesKey("show_battery_percent")
        private val SHOW_BATTERY_CURRENT = booleanPreferencesKey("show_battery_current")

        private val SHOW_SIGNAL = booleanPreferencesKey("show_signal")
        private val SHOW_SIGNAL_ICON = booleanPreferencesKey("show_signal_icon")
        private val SHOW_SIGNAL_BAND = booleanPreferencesKey("show_signal_band")
        private val SHOW_SIGNAL_CELL_ID = booleanPreferencesKey("show_signal_cell_id")

        private val SHOW_FRAME_DROPS = booleanPreferencesKey("show_frame_drops")
        private val SHOW_FPS = booleanPreferencesKey("show_fps")

        private val CONTROL_HZ = intPreferencesKey("control_hz")
        private val CONTROL_BUFFER_CAPACITY = intPreferencesKey("control_buffer_capacity")
        private val RENDER_QUEUE_SIZE = intPreferencesKey("render_queue_size")
        private val CONTROL_MODE = stringPreferencesKey("control_mode")
        private val FORWARD_SCALE = intPreferencesKey("forward_scale")
        private val BACKWARD_SCALE = intPreferencesKey("backward_scale")
        private val STEERING_SCALE = intPreferencesKey("steering_scale")

        private val MOTION_STEERING_DEG = intPreferencesKey("motion_steering_deg")
        private val MOTION_FORWARD_DEG = intPreferencesKey("motion_forward_deg")
        private val MOTION_BACKWARD_DEG = intPreferencesKey("motion_backward_deg")

        private val GAMEPAD_DEVICE_NAME = stringPreferencesKey("gamepad_device_name")
        private val GAMEPAD_STEERING_AXIS = intPreferencesKey("gamepad_steering_axis")
        private val GAMEPAD_STEERING_SIGN = intPreferencesKey("gamepad_steering_sign")
        private val GAMEPAD_THROTTLE_AXIS = intPreferencesKey("gamepad_throttle_axis")
        private val GAMEPAD_THROTTLE_SIGN = intPreferencesKey("gamepad_throttle_sign")
        private val GAMEPAD_REVERSE_AXIS = intPreferencesKey("gamepad_reverse_axis")
        private val GAMEPAD_REVERSE_SIGN = intPreferencesKey("gamepad_reverse_sign")
        private val GAMEPAD_STEERING_INVERT = booleanPreferencesKey("gamepad_steering_invert")
        private val GAMEPAD_THROTTLE_INVERT = booleanPreferencesKey("gamepad_throttle_invert")
        private val GAMEPAD_REVERSE_INVERT = booleanPreferencesKey("gamepad_reverse_invert")

        private val TOUCH_STEERING_INVERT = booleanPreferencesKey("touch_steering_invert")
        private val TOUCH_THROTTLE_INVERT = booleanPreferencesKey("touch_throttle_invert")
        private val MOTION_STEERING_INVERT = booleanPreferencesKey("motion_steering_invert")
        private val MOTION_THROTTLE_INVERT = booleanPreferencesKey("motion_throttle_invert")
    }

    val generalSettings: Flow<GeneralSettings> = context.dataStore.data.map { prefs ->
        val defaults = GeneralSettings()
        GeneralSettings(
            enableDebugStats = prefs[ENABLE_DEBUG_STATS] ?: defaults.enableDebugStats,
            showPipelineStats = prefs[SHOW_PIPELINE_STATS] ?: defaults.showPipelineStats,
            showSystemStats = prefs[SHOW_SYSTEM_STATS] ?: defaults.showSystemStats
        )
    }

    val networkSettings: Flow<NetworkSettings> = context.dataStore.data.map { prefs ->
        val defaults = NetworkSettings()
        NetworkSettings(
            relayUrl = prefs[RELAY_URL] ?: defaults.relayUrl,
            sessionId = prefs[SESSION_ID] ?: defaults.sessionId,
            spectatorMode = prefs[SPECTATOR_MODE] ?: defaults.spectatorMode,
            transport = Transport.fromString(prefs[TRANSPORT] ?: defaults.transport.name)
        )
    }

    val frequencySettings: Flow<FrequencySettings> = context.dataStore.data.map { prefs ->
        val defaults = FrequencySettings()
        FrequencySettings(
            controlHz = prefs[CONTROL_HZ] ?: defaults.controlHz,
            controlBufferCapacity = prefs[CONTROL_BUFFER_CAPACITY] ?: defaults.controlBufferCapacity,
            renderQueueSize = prefs[RENDER_QUEUE_SIZE] ?: defaults.renderQueueSize
        )
    }

    val osdSettings: Flow<OsdSettings> = context.dataStore.data.map { prefs ->
        val defaults = OsdSettings()
        OsdSettings(
            showPipelineTimer = prefs[SHOW_PIPELINE_TIMER] ?: defaults.showPipelineTimer,
            showBattery = prefs[SHOW_BATTERY] ?: defaults.showBattery,
            showBatteryIcon = prefs[SHOW_BATTERY_ICON] ?: defaults.showBatteryIcon,
            showBatteryVoltage = prefs[SHOW_BATTERY_VOLTAGE] ?: defaults.showBatteryVoltage,
            showBatteryCellVoltage = prefs[SHOW_BATTERY_CELL_VOLTAGE] ?: defaults.showBatteryCellVoltage,
            showBatteryPercent = prefs[SHOW_BATTERY_PERCENT] ?: defaults.showBatteryPercent,
            showBatteryCurrent = prefs[SHOW_BATTERY_CURRENT] ?: defaults.showBatteryCurrent,
            showSignal = prefs[SHOW_SIGNAL] ?: defaults.showSignal,
            showSignalIcon = prefs[SHOW_SIGNAL_ICON] ?: defaults.showSignalIcon,
            showSignalBand = prefs[SHOW_SIGNAL_BAND] ?: defaults.showSignalBand,
            showSignalCellId = prefs[SHOW_SIGNAL_CELL_ID] ?: defaults.showSignalCellId,
            showFrameDrops = prefs[SHOW_FRAME_DROPS] ?: defaults.showFrameDrops,
            showFps = prefs[SHOW_FPS] ?: defaults.showFps
        )
    }

    val controlSettings: Flow<ControlSettings> = context.dataStore.data.map { prefs ->
        val defaults = ControlSettings()
        ControlSettings(
            controlMode = prefs[CONTROL_MODE] ?: defaults.controlMode,
            forwardScale = prefs[FORWARD_SCALE] ?: defaults.forwardScale,
            backwardScale = prefs[BACKWARD_SCALE] ?: defaults.backwardScale,
            steeringScale = prefs[STEERING_SCALE] ?: defaults.steeringScale,
            motionSteeringDeg = prefs[MOTION_STEERING_DEG] ?: defaults.motionSteeringDeg,
            motionForwardDeg = prefs[MOTION_FORWARD_DEG] ?: defaults.motionForwardDeg,
            motionBackwardDeg = prefs[MOTION_BACKWARD_DEG] ?: defaults.motionBackwardDeg,
            gamepadDeviceName = prefs[GAMEPAD_DEVICE_NAME] ?: defaults.gamepadDeviceName,
            gamepadSteeringAxis = prefs[GAMEPAD_STEERING_AXIS] ?: defaults.gamepadSteeringAxis,
            gamepadSteeringSign = prefs[GAMEPAD_STEERING_SIGN] ?: defaults.gamepadSteeringSign,
            gamepadThrottleAxis = prefs[GAMEPAD_THROTTLE_AXIS] ?: defaults.gamepadThrottleAxis,
            gamepadThrottleSign = prefs[GAMEPAD_THROTTLE_SIGN] ?: defaults.gamepadThrottleSign,
            gamepadReverseAxis = prefs[GAMEPAD_REVERSE_AXIS] ?: defaults.gamepadReverseAxis,
            gamepadReverseSign = prefs[GAMEPAD_REVERSE_SIGN] ?: defaults.gamepadReverseSign,
            gamepadSteeringInvert = prefs[GAMEPAD_STEERING_INVERT] ?: defaults.gamepadSteeringInvert,
            gamepadThrottleInvert = prefs[GAMEPAD_THROTTLE_INVERT] ?: defaults.gamepadThrottleInvert,
            gamepadReverseInvert = prefs[GAMEPAD_REVERSE_INVERT] ?: defaults.gamepadReverseInvert,
            touchSteeringInvert = prefs[TOUCH_STEERING_INVERT] ?: defaults.touchSteeringInvert,
            touchThrottleInvert = prefs[TOUCH_THROTTLE_INVERT] ?: defaults.touchThrottleInvert,
            motionSteeringInvert = prefs[MOTION_STEERING_INVERT] ?: defaults.motionSteeringInvert,
            motionThrottleInvert = prefs[MOTION_THROTTLE_INVERT] ?: defaults.motionThrottleInvert
        )
    }

    suspend fun updateGeneralSettings(settings: GeneralSettings) {
        context.dataStore.edit { prefs ->
            prefs[ENABLE_DEBUG_STATS] = settings.enableDebugStats
            prefs[SHOW_PIPELINE_STATS] = settings.showPipelineStats
            prefs[SHOW_SYSTEM_STATS] = settings.showSystemStats
        }
    }

    suspend fun updateNetworkSettings(settings: NetworkSettings) {
        context.dataStore.edit { prefs ->
            prefs[RELAY_URL] = settings.relayUrl
            prefs[SESSION_ID] = settings.sessionId
            prefs[SPECTATOR_MODE] = settings.spectatorMode
            prefs[TRANSPORT] = settings.transport.name.lowercase()
        }
    }

    suspend fun updateFrequencySettings(settings: FrequencySettings) {
        context.dataStore.edit { prefs ->
            prefs[CONTROL_HZ] = settings.controlHz
            prefs[CONTROL_BUFFER_CAPACITY] = settings.controlBufferCapacity
            prefs[RENDER_QUEUE_SIZE] = settings.renderQueueSize
        }
    }

    suspend fun updateOsdSettings(settings: OsdSettings) {
        context.dataStore.edit { prefs ->
            prefs[SHOW_PIPELINE_TIMER] = settings.showPipelineTimer
            prefs[SHOW_BATTERY] = settings.showBattery
            prefs[SHOW_BATTERY_ICON] = settings.showBatteryIcon
            prefs[SHOW_BATTERY_VOLTAGE] = settings.showBatteryVoltage
            prefs[SHOW_BATTERY_CELL_VOLTAGE] = settings.showBatteryCellVoltage
            prefs[SHOW_BATTERY_PERCENT] = settings.showBatteryPercent
            prefs[SHOW_BATTERY_CURRENT] = settings.showBatteryCurrent
            prefs[SHOW_SIGNAL] = settings.showSignal
            prefs[SHOW_SIGNAL_ICON] = settings.showSignalIcon
            prefs[SHOW_SIGNAL_BAND] = settings.showSignalBand
            prefs[SHOW_SIGNAL_CELL_ID] = settings.showSignalCellId
            prefs[SHOW_FRAME_DROPS] = settings.showFrameDrops
            prefs[SHOW_FPS] = settings.showFps
        }
    }

    suspend fun updateControlSettings(settings: ControlSettings) {
        context.dataStore.edit { prefs ->
            prefs[CONTROL_MODE] = settings.controlMode
            prefs[FORWARD_SCALE] = settings.forwardScale
            prefs[BACKWARD_SCALE] = settings.backwardScale
            prefs[STEERING_SCALE] = settings.steeringScale
            prefs[MOTION_STEERING_DEG] = settings.motionSteeringDeg
            prefs[MOTION_FORWARD_DEG] = settings.motionForwardDeg
            prefs[MOTION_BACKWARD_DEG] = settings.motionBackwardDeg
            prefs[GAMEPAD_DEVICE_NAME] = settings.gamepadDeviceName
            prefs[GAMEPAD_STEERING_AXIS] = settings.gamepadSteeringAxis
            prefs[GAMEPAD_STEERING_SIGN] = settings.gamepadSteeringSign
            prefs[GAMEPAD_THROTTLE_AXIS] = settings.gamepadThrottleAxis
            prefs[GAMEPAD_THROTTLE_SIGN] = settings.gamepadThrottleSign
            prefs[GAMEPAD_REVERSE_AXIS] = settings.gamepadReverseAxis
            prefs[GAMEPAD_REVERSE_SIGN] = settings.gamepadReverseSign
            prefs[GAMEPAD_STEERING_INVERT] = settings.gamepadSteeringInvert
            prefs[GAMEPAD_THROTTLE_INVERT] = settings.gamepadThrottleInvert
            prefs[GAMEPAD_REVERSE_INVERT] = settings.gamepadReverseInvert
            prefs[TOUCH_STEERING_INVERT] = settings.touchSteeringInvert
            prefs[TOUCH_THROTTLE_INVERT] = settings.touchThrottleInvert
            prefs[MOTION_STEERING_INVERT] = settings.motionSteeringInvert
            prefs[MOTION_THROTTLE_INVERT] = settings.motionThrottleInvert
        }
    }
}
