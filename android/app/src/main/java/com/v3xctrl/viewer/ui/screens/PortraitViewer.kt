package com.v3xctrl.viewer.ui.screens

import android.view.SurfaceView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.ScreenRotation
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.v3xctrl.viewer.R
import com.v3xctrl.viewer.control.UDPReceiver
import com.v3xctrl.viewer.control.ViewerState
import com.v3xctrl.viewer.messages.Command
import com.v3xctrl.viewer.messages.Commands
import com.v3xctrl.viewer.ui.components.AppMenu
import com.v3xctrl.viewer.ui.widgets.LatencyIndicator
import com.v3xctrl.viewer.ui.widgets.RecordingIndicator

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PortraitViewer(
    surfaceView: SurfaceView,
    showVideoBlank: Boolean,
    viewerState: ViewerState,
    udpReceiver: UDPReceiver?,
    spectatorMode: Boolean,
    onBack: () -> Unit,
    onNavigateToNetwork: () -> Unit,
    onNavigateToFrequencies: () -> Unit,
    onNavigateToOSD: () -> Unit,
    onNavigateToControl: () -> Unit,
    modifier: Modifier = Modifier
) {
    var menuExpanded by remember { mutableStateOf(false) }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(Color.Black)
    ) {
        TopAppBar(
            title = { Text(stringResource(R.string.viewer_title)) },
            navigationIcon = {
                IconButton(onClick = onBack) {
                    Icon(
                        Icons.AutoMirrored.Filled.ArrowBack,
                        contentDescription = stringResource(R.string.back)
                    )
                }
            },
            actions = {
                IconButton(onClick = { menuExpanded = true }) {
                    Icon(Icons.Default.MoreVert, contentDescription = stringResource(R.string.menu))
                }
                AppMenu(
                    expanded = menuExpanded,
                    onDismiss = { menuExpanded = false },
                    onNavigateToNetwork = onNavigateToNetwork,
                    onNavigateToFrequencies = onNavigateToFrequencies,
                    onNavigateToOSD = onNavigateToOSD,
                    onNavigateToControl = onNavigateToControl
                )
            },
            colors = TopAppBarDefaults.topAppBarColors(
                containerColor = Color.Black,
                titleContentColor = Color.White,
                navigationIconContentColor = Color.White,
                actionIconContentColor = Color.White
            )
        )

        // Video with 16:9 aspect ratio and status indicator overlay
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(16f / 9f)
        ) {
            VideoSurface(
                surfaceView = surfaceView,
                showVideoBlank = showVideoBlank,
                modifier = Modifier.fillMaxSize()
            )

            // Connection status indicator dot (top-left corner)
            if (viewerState.isControlConnected) {
                LatencyIndicator(
                    latencyStatus = viewerState.latencyStatus,
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .offset(x = 12.dp, y = 12.dp)
                )
            }

            // Recording indicator (bottom-right)
            if (viewerState.isRecording) {
                RecordingIndicator(
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .offset(x = (-12).dp, y = (-12).dp)
                )
            }
        }

        // Scrollable controls area below video
        Column(
            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
        ) {
            // Rotation hint directly below video
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 16.dp),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Default.ScreenRotation,
                    contentDescription = null,
                    tint = Color.White,
                    modifier = Modifier.size(24.dp)
                )
                Text(
                    text = stringResource(R.string.rotate_hint),
                    color = Color.White,
                    modifier = Modifier.padding(start = 8.dp)
                )
            }

            // Control buttons - only show when connected and not in spectator mode
            if (viewerState.isControlConnected && !spectatorMode) {
                ControlButtons(
                    viewerState = viewerState,
                    onCommand = { command ->
                        udpReceiver?.sendCommand(command) { success ->
                            // Command acknowledgment callback
                            // Could show toast on failure
                        }
                    },
                    onDisconnect = onBack
                )
            }
        }
    }
}

@Composable
private fun ControlButtons(
    viewerState: ViewerState,
    onCommand: (Command) -> Unit,
    onDisconnect: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // Row 1: Video and Recording buttons (50/50)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // Video button - toggles based on state
            if (viewerState.isVideoRunning) {
                OutlinedButton(
                    onClick = { onCommand(Commands.videoStop()) },
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = Color.Red
                    ),
                    modifier = Modifier.weight(1f)
                ) {
                    Text(stringResource(R.string.btn_stop_video))
                }
            } else {
                Button(
                    onClick = { onCommand(Commands.videoStart()) },
                    modifier = Modifier.weight(1f)
                ) {
                    Text(stringResource(R.string.btn_start_video))
                }
            }

            // Recording button - toggles based on state
            if (viewerState.isRecording) {
                OutlinedButton(
                    onClick = { onCommand(Commands.recordingStop()) },
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = Color.Red
                    ),
                    modifier = Modifier.weight(1f)
                ) {
                    Text(stringResource(R.string.btn_stop_recording))
                }
            } else {
                Button(
                    onClick = { onCommand(Commands.recordingStart()) },
                    enabled = viewerState.isVideoRunning,
                    modifier = Modifier.weight(1f)
                ) {
                    Text(stringResource(R.string.btn_start_recording))
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Row 2: Trim buttons (50/50)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedButton(
                onClick = { onCommand(Commands.trimDecrease()) },
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = Color.White
                ),
                modifier = Modifier.weight(1f)
            ) {
                Text(stringResource(R.string.btn_trim_minus))
            }

            OutlinedButton(
                onClick = { onCommand(Commands.trimIncrease()) },
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = Color.White
                ),
                modifier = Modifier.weight(1f)
            ) {
                Text(stringResource(R.string.btn_trim_plus))
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Row 3: Shutdown and Reboot (shutdown on left, reboot on right)
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedButton(
                onClick = { onCommand(Commands.shutdown()) },
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = Color.Red
                ),
                modifier = Modifier.weight(1f)
            ) {
                Text(stringResource(R.string.btn_shutdown))
            }

            OutlinedButton(
                onClick = { onCommand(Commands.restart()) },
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = Color.Yellow
                ),
                modifier = Modifier.weight(1f)
            ) {
                Text(stringResource(R.string.btn_reboot))
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Row 4: Disconnect (100% width)
        OutlinedButton(
            onClick = onDisconnect,
            colors = ButtonDefaults.outlinedButtonColors(
                contentColor = Color.Gray
            ),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(stringResource(R.string.btn_disconnect))
        }
    }
}
