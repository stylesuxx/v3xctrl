package com.v3xctrl.viewer.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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
                .padding(16.dp)
        ) {
            // Battery main toggle
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSettingsChange(settings.copy(showBattery = !settings.showBattery)) }
                    .padding(vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = stringResource(R.string.osd_battery),
                        style = MaterialTheme.typography.bodyLarge
                    )

                    Text(
                        text = stringResource(R.string.osd_battery_desc),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                Switch(
                    checked = settings.showBattery,
                    onCheckedChange = { onSettingsChange(settings.copy(showBattery = it)) }
                )
            }

            // Battery sub-toggles (only interactive when battery is enabled)
            if (settings.showBattery) {
                BatterySubToggle(
                    label = stringResource(R.string.osd_battery_icon),
                    checked = settings.showBatteryIcon,
                    onCheckedChange = { onSettingsChange(settings.copy(showBatteryIcon = it)) }
                )

                BatterySubToggle(
                    label = stringResource(R.string.osd_battery_voltage),
                    checked = settings.showBatteryVoltage,
                    onCheckedChange = { onSettingsChange(settings.copy(showBatteryVoltage = it)) }
                )

                BatterySubToggle(
                    label = stringResource(R.string.osd_battery_cell_voltage),
                    checked = settings.showBatteryCellVoltage,
                    onCheckedChange = { onSettingsChange(settings.copy(showBatteryCellVoltage = it)) }
                )

                BatterySubToggle(
                    label = stringResource(R.string.osd_battery_percent),
                    checked = settings.showBatteryPercent,
                    onCheckedChange = { onSettingsChange(settings.copy(showBatteryPercent = it)) }
                )

                BatterySubToggle(
                    label = stringResource(R.string.osd_battery_current),
                    checked = settings.showBatteryCurrent,
                    onCheckedChange = { onSettingsChange(settings.copy(showBatteryCurrent = it)) }
                )
            }

            // Pipeline Timer toggle
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onSettingsChange(settings.copy(showPipelineTimer = !settings.showPipelineTimer)) }
                    .padding(vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = stringResource(R.string.osd_pipeline_timer),
                        style = MaterialTheme.typography.bodyLarge
                    )

                    Text(
                        text = stringResource(R.string.osd_pipeline_timer_desc),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                Switch(
                    checked = settings.showPipelineTimer,
                    onCheckedChange = { onSettingsChange(settings.copy(showPipelineTimer = it)) }
                )
            }
        }
    }
}

@Composable
private fun BatterySubToggle(
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
