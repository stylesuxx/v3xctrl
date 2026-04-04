package com.v3xctrl.viewer.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.v3xctrl.viewer.R
import com.v3xctrl.viewer.data.FrequencySettings
import com.v3xctrl.viewer.ui.theme.V3xctrlTheme

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FrequenciesScreen(
    settings: FrequencySettings,
    onSettingsChange: (FrequencySettings) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    Scaffold(
        modifier = modifier.fillMaxSize(),
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.frequencies_title)) },
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
        var controlHzText by remember { mutableStateOf(settings.controlHz.toString()) }
        var controlBufferCapacityText by remember { mutableStateOf(settings.controlBufferCapacity.toString()) }
        var renderQueueSizeText by remember { mutableStateOf(settings.renderQueueSize.toString()) }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            OutlinedTextField(
                value = controlHzText,
                onValueChange = { input ->
                    val filtered = input.filter { c -> c.isDigit() }
                    controlHzText = filtered
                    val value = filtered.toIntOrNull()
                    if (value != null) {
                        onSettingsChange(settings.copy(controlHz = value.coerceIn(1, 100)))
                    }
                },
                label = { Text(stringResource(R.string.control_hz)) },
                suffix = { Text("Hz") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = stringResource(R.string.control_hz_description),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            Spacer(modifier = Modifier.height(16.dp))

            OutlinedTextField(
                value = controlBufferCapacityText,
                onValueChange = { input ->
                    val filtered = input.filter { c -> c.isDigit() }
                    controlBufferCapacityText = filtered
                    val value = filtered.toIntOrNull()
                    if (value != null) {
                        onSettingsChange(settings.copy(controlBufferCapacity = value.coerceIn(1, 100)))
                    }
                },
                label = { Text(stringResource(R.string.control_buffer_capacity)) },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = stringResource(R.string.control_buffer_capacity_description),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            Spacer(modifier = Modifier.height(16.dp))

            OutlinedTextField(
                value = renderQueueSizeText,
                onValueChange = { input ->
                    val filtered = input.filter { c -> c.isDigit() }
                    renderQueueSizeText = filtered
                    val value = filtered.toIntOrNull()
                    if (value != null) {
                        onSettingsChange(settings.copy(renderQueueSize = value.coerceIn(0, 30)))
                    }
                },
                label = { Text(stringResource(R.string.render_queue_size)) },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = stringResource(R.string.render_queue_size_description),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Preview(showBackground = true)
@Composable
fun FrequenciesScreenPreview() {
    V3xctrlTheme {
        FrequenciesScreen(
            settings = FrequencySettings(),
            onSettingsChange = {},
            onBack = {}
        )
    }
}
