package com.v3xctrl.viewer.ui.screens

import android.view.InputDevice
import android.view.MotionEvent
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.MenuAnchorType
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import android.content.Context
import android.hardware.input.InputManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import com.v3xctrl.viewer.MainActivity
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.v3xctrl.viewer.R
import com.v3xctrl.viewer.data.ControlSettings
import kotlin.math.abs
import kotlin.math.roundToInt

private val CONTROL_MODES = listOf("touch", "motion", "gamepad")

private val AXES_TO_CHECK = intArrayOf(
    MotionEvent.AXIS_X,
    MotionEvent.AXIS_Y,
    MotionEvent.AXIS_Z,
    MotionEvent.AXIS_RZ,
    MotionEvent.AXIS_LTRIGGER,
    MotionEvent.AXIS_RTRIGGER,
    MotionEvent.AXIS_HAT_X,
    MotionEvent.AXIS_HAT_Y
)

private fun scanGamepads(): List<InputDevice> =
    InputDevice.getDeviceIds()
        .toList()
        .mapNotNull { InputDevice.getDevice(it) }
        .filter { device ->
            device.sources and InputDevice.SOURCE_JOYSTICK == InputDevice.SOURCE_JOYSTICK ||
                device.sources and InputDevice.SOURCE_GAMEPAD == InputDevice.SOURCE_GAMEPAD
        }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ControlScreen(
    settings: ControlSettings,
    onSettingsChange: (ControlSettings) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val activity = context as? MainActivity

    Scaffold(
        modifier = modifier.fillMaxSize(),
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.control_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.back)
                        )
                    }
                }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            // -- Control Mode dropdown --
            var expanded by remember { mutableStateOf(false) }

            ExposedDropdownMenuBox(
                expanded = expanded,
                onExpandedChange = { expanded = it }
            ) {
                OutlinedTextField(
                    value = settings.controlMode.replaceFirstChar { it.uppercase() },
                    onValueChange = {},
                    readOnly = true,
                    label = { Text(stringResource(R.string.control_mode_label)) },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .menuAnchor(MenuAnchorType.PrimaryNotEditable)
                )

                ExposedDropdownMenu(
                    expanded = expanded,
                    onDismissRequest = { expanded = false }
                ) {
                    CONTROL_MODES.forEach { mode ->
                        DropdownMenuItem(
                            text = { Text(mode.replaceFirstChar { it.uppercase() }) },
                            onClick = {
                                onSettingsChange(settings.copy(controlMode = mode))
                                expanded = false
                            }
                        )
                    }
                }
            }

            Text(
                text = stringResource(
                    when (settings.controlMode) {
                        "motion" -> R.string.control_mode_motion_desc
                        "gamepad" -> R.string.control_mode_gamepad_desc
                        else -> R.string.control_mode_touch_desc
                    }
                ),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 8.dp)
            )

            // -- Gamepad device selector, calibration, and live display --
            if (settings.controlMode == "gamepad") {
                Spacer(modifier = Modifier.height(16.dp))

                var gamepads by remember { mutableStateOf(scanGamepads()) }

                DisposableEffect(Unit) {
                    val inputManager = context.getSystemService(Context.INPUT_SERVICE) as InputManager
                    val listener = object : InputManager.InputDeviceListener {
                        override fun onInputDeviceAdded(deviceId: Int) { gamepads = scanGamepads() }
                        override fun onInputDeviceRemoved(deviceId: Int) { gamepads = scanGamepads() }
                        override fun onInputDeviceChanged(deviceId: Int) { gamepads = scanGamepads() }
                    }
                    inputManager.registerInputDeviceListener(listener, null)
                    onDispose { inputManager.unregisterInputDeviceListener(listener) }
                }

                if (gamepads.isEmpty()) {
                    Text(
                        text = stringResource(R.string.control_no_gamepads),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                } else {
                    var gamepadExpanded by remember { mutableStateOf(false) }
                    val displayName = settings.gamepadDeviceName.ifEmpty {
                        stringResource(R.string.control_select_gamepad)
                    }

                    ExposedDropdownMenuBox(
                        expanded = gamepadExpanded,
                        onExpandedChange = { gamepadExpanded = it }
                    ) {
                        OutlinedTextField(
                            value = displayName,
                            onValueChange = {},
                            readOnly = true,
                            label = { Text(stringResource(R.string.control_gamepad_device)) },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = gamepadExpanded) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .menuAnchor(MenuAnchorType.PrimaryNotEditable)
                        )

                        ExposedDropdownMenu(
                            expanded = gamepadExpanded,
                            onDismissRequest = { gamepadExpanded = false }
                        ) {
                            gamepads.forEach { device ->
                                DropdownMenuItem(
                                    text = { Text(device.name) },
                                    onClick = {
                                        onSettingsChange(settings.copy(gamepadDeviceName = device.name))
                                        gamepadExpanded = false
                                    }
                                )
                            }
                        }
                    }

                    // Calibration and live display (when a device is selected)
                    if (settings.gamepadDeviceName.isNotEmpty()) {
                        Spacer(modifier = Modifier.height(16.dp))

                        // Calibration state
                        val isCalibrating = remember { mutableStateOf(false) }
                        val calibrationStep = remember { mutableIntStateOf(0) }
                        val axisRanges = remember { Array(AXES_TO_CHECK.size) { floatArrayOf(Float.MAX_VALUE, Float.MIN_VALUE) } }
                        val lastAxisValues = remember { FloatArray(AXES_TO_CHECK.size) }
                        val detectedRange = remember { mutableFloatStateOf(0f) }
                        val calSteeringAxis = remember { mutableIntStateOf(0) }
                        val calSteeringSign = remember { mutableIntStateOf(1) }
                        val calThrottleAxis = remember { mutableIntStateOf(0) }
                        val calThrottleSign = remember { mutableIntStateOf(1) }

                        // Live display state
                        val liveSteering = remember { mutableFloatStateOf(0f) }
                        val liveThrottle = remember { mutableFloatStateOf(0f) }

                        // Keep current settings in State for the listener
                        val curSettings = rememberUpdatedState(settings)
                        val curOnSettingsChange = rememberUpdatedState(onSettingsChange)

                        // Resolve device name to ID
                        val selectedDeviceId = remember(settings.gamepadDeviceName) {
                            InputDevice.getDeviceIds()
                                .toList()
                                .mapNotNull { InputDevice.getDevice(it) }
                                .firstOrNull { it.name == settings.gamepadDeviceName }
                                ?.id
                        }

                        // Single handler for both calibration and live display
                        DisposableEffect(selectedDeviceId) {
                            activity?.onGamepadMotionEvent = { event ->
                                if (event.source and InputDevice.SOURCE_JOYSTICK == InputDevice.SOURCE_JOYSTICK &&
                                    event.action == MotionEvent.ACTION_MOVE &&
                                    (selectedDeviceId == null || event.deviceId == selectedDeviceId)
                                ) {
                                    if (isCalibrating.value) {
                                        var maxRange = 0f
                                        for (i in AXES_TO_CHECK.indices) {
                                            val v = event.getAxisValue(AXES_TO_CHECK[i])
                                            if (v < axisRanges[i][0]) axisRanges[i][0] = v
                                            if (v > axisRanges[i][1]) axisRanges[i][1] = v
                                            lastAxisValues[i] = v
                                            val range = axisRanges[i][1] - axisRanges[i][0]
                                            if (range > maxRange) maxRange = range
                                        }
                                        detectedRange.floatValue = maxRange
                                    } else {
                                        // Live display
                                        val s = curSettings.value
                                        val sRaw = event.getAxisValue(s.gamepadSteeringAxis) * s.gamepadSteeringSign
                                        val tRaw = if (s.gamepadThrottleAxis == s.gamepadReverseAxis) {
                                            event.getAxisValue(s.gamepadThrottleAxis) * s.gamepadThrottleSign
                                        } else {
                                            val forward = (event.getAxisValue(s.gamepadThrottleAxis) * s.gamepadThrottleSign)
                                                .coerceAtLeast(0f)
                                            val backward = (event.getAxisValue(s.gamepadReverseAxis) * s.gamepadReverseSign)
                                                .coerceAtLeast(0f)
                                            forward - backward
                                        }
                                        liveSteering.floatValue = sRaw.coerceIn(-1f, 1f)
                                        liveThrottle.floatValue = tRaw.coerceIn(-1f, 1f)
                                    }
                                    true
                                } else {
                                    false
                                }
                            }

                            onDispose {
                                activity?.onGamepadMotionEvent = null
                            }
                        }

                        if (isCalibrating.value) {
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.secondaryContainer
                                )
                            ) {
                                Column(modifier = Modifier.padding(16.dp)) {
                                    Text(
                                        text = stringResource(R.string.control_calibrate) +
                                            " \u2014 ${calibrationStep.intValue + 1}/3",
                                        style = MaterialTheme.typography.titleMedium
                                    )

                                    Spacer(modifier = Modifier.height(8.dp))

                                    Text(
                                        text = stringResource(
                                            when (calibrationStep.intValue) {
                                                0 -> R.string.control_calibrate_steering
                                                1 -> R.string.control_calibrate_throttle
                                                else -> R.string.control_calibrate_reverse
                                            }
                                        ),
                                        style = MaterialTheme.typography.bodyMedium
                                    )

                                    Spacer(modifier = Modifier.height(12.dp))

                                    LinearProgressIndicator(
                                        progress = { (detectedRange.floatValue / 2f).coerceIn(0f, 1f) },
                                        modifier = Modifier.fillMaxWidth()
                                    )

                                    Spacer(modifier = Modifier.height(12.dp))
                                    Row {
                                        Button(
                                            onClick = {
                                                var bestIdx = 0
                                                var bestRange = 0f
                                                for (i in AXES_TO_CHECK.indices) {
                                                    val range = axisRanges[i][1] - axisRanges[i][0]
                                                    if (range > bestRange) {
                                                        bestRange = range
                                                        bestIdx = i
                                                    }
                                                }
                                                val axis = AXES_TO_CHECK[bestIdx]
                                                val sign = if (lastAxisValues[bestIdx] >= 0f) 1 else -1

                                                when (calibrationStep.intValue) {
                                                    0 -> {
                                                        calSteeringAxis.intValue = axis
                                                        calSteeringSign.intValue = sign
                                                    }
                                                    1 -> {
                                                        calThrottleAxis.intValue = axis
                                                        calThrottleSign.intValue = sign
                                                    }
                                                    2 -> {
                                                        curOnSettingsChange.value(
                                                            curSettings.value.copy(
                                                                gamepadSteeringAxis = calSteeringAxis.intValue,
                                                                gamepadSteeringSign = calSteeringSign.intValue,
                                                                gamepadThrottleAxis = calThrottleAxis.intValue,
                                                                gamepadThrottleSign = calThrottleSign.intValue,
                                                                gamepadReverseAxis = axis,
                                                                gamepadReverseSign = sign
                                                            )
                                                        )
                                                    }
                                                }

                                                if (calibrationStep.intValue < 2) {
                                                    calibrationStep.intValue++
                                                    for (i in AXES_TO_CHECK.indices) {
                                                        axisRanges[i][0] = Float.MAX_VALUE
                                                        axisRanges[i][1] = Float.MIN_VALUE
                                                    }
                                                    detectedRange.floatValue = 0f
                                                } else {
                                                    isCalibrating.value = false
                                                    calibrationStep.intValue = 0
                                                }
                                            },
                                            enabled = detectedRange.floatValue > 0.1f
                                        ) {
                                            Text(stringResource(R.string.ok))
                                        }

                                        Spacer(modifier = Modifier.width(8.dp))

                                        TextButton(onClick = {
                                            isCalibrating.value = false
                                            calibrationStep.intValue = 0
                                            for (i in AXES_TO_CHECK.indices) {
                                                axisRanges[i][0] = Float.MAX_VALUE
                                                axisRanges[i][1] = Float.MIN_VALUE
                                            }
                                            detectedRange.floatValue = 0f
                                        }) {
                                            Text(stringResource(R.string.abort))
                                        }
                                    }
                                }
                            }
                        } else {
                            Button(
                                onClick = {
                                    isCalibrating.value = true
                                    calibrationStep.intValue = 0
                                    for (i in AXES_TO_CHECK.indices) {
                                        axisRanges[i][0] = Float.MAX_VALUE
                                        axisRanges[i][1] = Float.MIN_VALUE
                                    }
                                    detectedRange.floatValue = 0f
                                },
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Text(stringResource(R.string.control_calibrate))
                            }
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        // Live axis indicators
                        AxisIndicator(
                            label = stringResource(R.string.control_gamepad_steering),
                            value = liveSteering.floatValue
                        )

                        AxisIndicator(
                            label = stringResource(R.string.control_gamepad_throttle),
                            value = liveThrottle.floatValue
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // -- Output Scale --
            Text(
                text = stringResource(R.string.control_scale_section),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(bottom = 8.dp)
            )

            LabeledSlider(
                label = stringResource(R.string.control_forward_scale),
                value = settings.forwardScale,
                onValueChange = { onSettingsChange(settings.copy(forwardScale = it)) },
                valueRange = 0f..100f,
                suffix = "%"
            )

            LabeledSlider(
                label = stringResource(R.string.control_backward_scale),
                value = settings.backwardScale,
                onValueChange = { onSettingsChange(settings.copy(backwardScale = it)) },
                valueRange = 0f..100f,
                suffix = "%"
            )

            LabeledSlider(
                label = stringResource(R.string.control_steering_scale),
                value = settings.steeringScale,
                onValueChange = { onSettingsChange(settings.copy(steeringScale = it)) },
                valueRange = 0f..100f,
                suffix = "%"
            )

            // -- Motion Settings (only visible when motion mode selected) --
            if (settings.controlMode == "motion") {
                Spacer(modifier = Modifier.height(24.dp))

                Text(
                    text = stringResource(R.string.control_motion_section),
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(bottom = 8.dp)
                )

                LabeledSlider(
                    label = stringResource(R.string.control_motion_steering_deg),
                    value = settings.motionSteeringDeg,
                    onValueChange = { onSettingsChange(settings.copy(motionSteeringDeg = it)) },
                    valueRange = 10f..90f,
                    suffix = "\u00B0"
                )

                LabeledSlider(
                    label = stringResource(R.string.control_motion_forward_deg),
                    value = settings.motionForwardDeg,
                    onValueChange = { onSettingsChange(settings.copy(motionForwardDeg = it)) },
                    valueRange = 10f..90f,
                    suffix = "\u00B0"
                )

                LabeledSlider(
                    label = stringResource(R.string.control_motion_backward_deg),
                    value = settings.motionBackwardDeg,
                    onValueChange = { onSettingsChange(settings.copy(motionBackwardDeg = it)) },
                    valueRange = 10f..90f,
                    suffix = "\u00B0"
                )
            }
        }
    }
}

@Composable
private fun AxisIndicator(
    label: String,
    value: Float,
    modifier: Modifier = Modifier
) {
    val primaryColor = MaterialTheme.colorScheme.primary
    val trackColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.1f)
    val centerColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f)

    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.width(72.dp)
        )

        Canvas(
            modifier = Modifier
                .weight(1f)
                .height(20.dp)
                .padding(horizontal = 4.dp)
        ) {
            val w = size.width
            val h = size.height
            val centerX = w / 2f

            // Background track
            drawRoundRect(
                color = trackColor,
                cornerRadius = CornerRadius(4f, 4f)
            )

            // Center line
            drawLine(
                color = centerColor,
                start = Offset(centerX, 0f),
                end = Offset(centerX, h),
                strokeWidth = 1f
            )

            // Value bar from center
            val valueX = ((value + 1f) / 2f) * w
            if (value != 0f) {
                drawRect(
                    color = primaryColor.copy(alpha = 0.4f),
                    topLeft = Offset(minOf(centerX, valueX), 2f),
                    size = Size(abs(valueX - centerX), h - 4f)
                )
            }

            // Value marker
            drawLine(
                color = primaryColor,
                start = Offset(valueX, 0f),
                end = Offset(valueX, h),
                strokeWidth = 3f
            )
        }

        Text(
            text = "%+.2f".format(value),
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.width(48.dp),
            textAlign = TextAlign.End
        )
    }
}

@Composable
private fun LabeledSlider(
    label: String,
    value: Int,
    onValueChange: (Int) -> Unit,
    valueRange: ClosedFloatingPointRange<Float>,
    suffix: String
) {
    Column(modifier = Modifier.padding(vertical = 4.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.weight(1f)
            )

            Text(
                text = "$value$suffix",
                style = MaterialTheme.typography.bodyMedium
            )
        }
        Slider(
            value = value.toFloat(),
            onValueChange = { onValueChange(it.roundToInt()) },
            valueRange = valueRange,
            modifier = Modifier.fillMaxWidth()
        )
    }
}
