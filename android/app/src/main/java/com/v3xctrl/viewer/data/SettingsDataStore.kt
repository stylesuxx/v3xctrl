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

data class NetworkSettings(
    val relayUrl: String = "relay.v3xctrl.com:8888",
    val sessionId: String = "",
    val spectatorMode: Boolean = false
)

data class FrequencySettings(
    val controlHz: Int = 30
)

data class OsdSettings(
    val showPipelineTimer: Boolean = false
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
    val gamepadReverseSign: Int = 1
)

class SettingsDataStore(private val context: Context) {

    companion object {
        private val RELAY_URL = stringPreferencesKey("relay_url")
        private val SESSION_ID = stringPreferencesKey("session_id")
        private val SPECTATOR_MODE = booleanPreferencesKey("spectator_mode")
        private val CONTROL_HZ = intPreferencesKey("control_hz")
        private val SHOW_PIPELINE_TIMER = booleanPreferencesKey("show_pipeline_timer")
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
    }

    val networkSettings: Flow<NetworkSettings> = context.dataStore.data.map { prefs ->
        val defaults = NetworkSettings()
        NetworkSettings(
            relayUrl = prefs[RELAY_URL] ?: defaults.relayUrl,
            sessionId = prefs[SESSION_ID] ?: defaults.sessionId,
            spectatorMode = prefs[SPECTATOR_MODE] ?: defaults.spectatorMode
        )
    }

    val frequencySettings: Flow<FrequencySettings> = context.dataStore.data.map { prefs ->
        val defaults = FrequencySettings()
        FrequencySettings(
            controlHz = prefs[CONTROL_HZ] ?: defaults.controlHz
        )
    }

    val osdSettings: Flow<OsdSettings> = context.dataStore.data.map { prefs ->
        val defaults = OsdSettings()
        OsdSettings(
            showPipelineTimer = prefs[SHOW_PIPELINE_TIMER] ?: defaults.showPipelineTimer
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
            gamepadReverseSign = prefs[GAMEPAD_REVERSE_SIGN] ?: defaults.gamepadReverseSign
        )
    }

    suspend fun updateNetworkSettings(settings: NetworkSettings) {
        context.dataStore.edit { prefs ->
            prefs[RELAY_URL] = settings.relayUrl
            prefs[SESSION_ID] = settings.sessionId
            prefs[SPECTATOR_MODE] = settings.spectatorMode
        }
    }

    suspend fun updateFrequencySettings(settings: FrequencySettings) {
        context.dataStore.edit { prefs ->
            prefs[CONTROL_HZ] = settings.controlHz
        }
    }

    suspend fun updateOsdSettings(settings: OsdSettings) {
        context.dataStore.edit { prefs ->
            prefs[SHOW_PIPELINE_TIMER] = settings.showPipelineTimer
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
        }
    }
}
