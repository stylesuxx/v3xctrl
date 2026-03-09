package com.v3xctrl.viewer.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.v3xctrl.viewer.R
import com.v3xctrl.viewer.data.OsdSettings

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OSDScreen(
    settings: OsdSettings,
    onSettingsChange: (OsdSettings) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    Scaffold(
        modifier = modifier.fillMaxSize(),
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.osd_title)) },
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
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            // Battery main toggle
            MainToggle(
                title = stringResource(R.string.osd_battery),
                description = stringResource(R.string.osd_battery_desc),
                checked = settings.showBattery,
                onCheckedChange = { onSettingsChange(settings.copy(showBattery = it)) }
            )

            // Battery sub-toggles (only interactive when battery is enabled)
            if (settings.showBattery) {
                SubToggle(
                    label = stringResource(R.string.osd_battery_icon),
                    checked = settings.showBatteryIcon,
                    onCheckedChange = { onSettingsChange(settings.copy(showBatteryIcon = it)) }
                )

                SubToggle(
                    label = stringResource(R.string.osd_battery_voltage),
                    checked = settings.showBatteryVoltage,
                    onCheckedChange = { onSettingsChange(settings.copy(showBatteryVoltage = it)) }
                )

                SubToggle(
                    label = stringResource(R.string.osd_battery_cell_voltage),
                    checked = settings.showBatteryCellVoltage,
                    onCheckedChange = { onSettingsChange(settings.copy(showBatteryCellVoltage = it)) }
                )

                SubToggle(
                    label = stringResource(R.string.osd_battery_percent),
                    checked = settings.showBatteryPercent,
                    onCheckedChange = { onSettingsChange(settings.copy(showBatteryPercent = it)) }
                )

                SubToggle(
                    label = stringResource(R.string.osd_battery_current),
                    checked = settings.showBatteryCurrent,
                    onCheckedChange = { onSettingsChange(settings.copy(showBatteryCurrent = it)) }
                )
            }

            // Signal main toggle
            MainToggle(
                title = stringResource(R.string.osd_signal),
                description = stringResource(R.string.osd_signal_desc),
                checked = settings.showSignal,
                onCheckedChange = { onSettingsChange(settings.copy(showSignal = it)) }
            )

            // Signal sub-toggles
            if (settings.showSignal) {
                SubToggle(
                    label = stringResource(R.string.osd_signal_icon),
                    checked = settings.showSignalIcon,
                    onCheckedChange = { onSettingsChange(settings.copy(showSignalIcon = it)) }
                )

                SubToggle(
                    label = stringResource(R.string.osd_signal_band),
                    checked = settings.showSignalBand,
                    onCheckedChange = { onSettingsChange(settings.copy(showSignalBand = it)) }
                )

                SubToggle(
                    label = stringResource(R.string.osd_signal_cell_id),
                    checked = settings.showSignalCellId,
                    onCheckedChange = { onSettingsChange(settings.copy(showSignalCellId = it)) }
                )
            }

            // Frame Drops toggle
            MainToggle(
                title = stringResource(R.string.osd_frame_drops),
                description = stringResource(R.string.osd_frame_drops_desc),
                checked = settings.showFrameDrops,
                onCheckedChange = { onSettingsChange(settings.copy(showFrameDrops = it)) }
            )

            // FPS Counter toggle
            MainToggle(
                title = stringResource(R.string.osd_fps),
                description = stringResource(R.string.osd_fps_desc),
                checked = settings.showFps,
                onCheckedChange = { onSettingsChange(settings.copy(showFps = it)) }
            )

            // Pipeline Timer toggle
            MainToggle(
                title = stringResource(R.string.osd_pipeline_timer),
                description = stringResource(R.string.osd_pipeline_timer_desc),
                checked = settings.showPipelineTimer,
                onCheckedChange = { onSettingsChange(settings.copy(showPipelineTimer = it)) }
            )
        }
    }
}

@Composable
private fun MainToggle(
    title: String,
    description: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onCheckedChange(!checked) }
            .padding(vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyLarge
            )

            Text(
                text = description,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange
        )
    }
}

@Composable
private fun SubToggle(
    label: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onCheckedChange(!checked) }
            .padding(start = 32.dp, top = 4.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f)
        )

        Checkbox(
            checked = checked,
            onCheckedChange = onCheckedChange
        )
    }
}
