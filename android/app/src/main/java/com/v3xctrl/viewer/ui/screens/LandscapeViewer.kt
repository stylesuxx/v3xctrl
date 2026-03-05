package com.v3xctrl.viewer.ui.screens

import android.view.SurfaceView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.v3xctrl.viewer.R
import com.v3xctrl.viewer.control.ControlState
import com.v3xctrl.viewer.control.ViewerState
import com.v3xctrl.viewer.data.OsdSettings
import com.v3xctrl.viewer.input.MotionController
import com.v3xctrl.viewer.ui.components.TouchControls
import com.v3xctrl.viewer.ui.widgets.BatteryWidget
import com.v3xctrl.viewer.ui.widgets.FpsCounter
import com.v3xctrl.viewer.ui.widgets.FrameDropIndicator
import com.v3xctrl.viewer.ui.widgets.PipelineTimer
import com.v3xctrl.viewer.ui.widgets.RecordingIndicator
import com.v3xctrl.viewer.ui.widgets.SignalStrengthWidget

@Composable
fun LandscapeViewer(
    surfaceView: SurfaceView,
    showVideoBlank: Boolean,
    controlState: ControlState,
    viewerState: ViewerState,
    motionController: MotionController?,
    isMotionMode: Boolean,
    isGamepadMode: Boolean,
    spectatorMode: Boolean,
    pipelineStartTime: Long,
    osdSettings: OsdSettings = OsdSettings(),
    fps: Int = 0,
    touchSteeringInvert: Boolean = false,
    touchThrottleInvert: Boolean = false,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Color.Black)
    ) {
        VideoSurface(
            surfaceView = surfaceView,
            showVideoBlank = showVideoBlank,
            modifier = Modifier.fillMaxSize()
        )

        // Status messages (center, stacked)
        if (showVideoBlank || viewerState.isControlTimedOut) {
            Column(
                modifier = Modifier
                    .align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                if (showVideoBlank) {
                    Text(
                        text = stringResource(R.string.no_video_signal),
                        color = Color.Gray
                    )
                }
                if (viewerState.isControlTimedOut) {
                    Text(
                        text = stringResource(R.string.no_control_signal),
                        color = Color.Gray
                    )
                }
            }
        }

        // Telemetry widgets (hidden when control signal is lost)
        if (!viewerState.isControlTimedOut) {
            // Frame drop indicator (top-center)
            if (osdSettings.showFrameDrops && viewerState.isUdpOverrun) {
                FrameDropIndicator(
                    modifier = Modifier
                        .align(Alignment.TopCenter)
                        .offset(y = 12.dp)
                )
            }

            // Signal strength widget (top-left)
            if (osdSettings.showSignal) {
                SignalStrengthWidget(
                    rsrp = viewerState.signalRsrp,
                    rsrq = viewerState.signalRsrq,
                    band = viewerState.signalBand,
                    cellId = viewerState.signalCellId,
                    showIcon = osdSettings.showSignalIcon,
                    showBand = osdSettings.showSignalBand,
                    showCellId = osdSettings.showSignalCellId,
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .offset(x = 12.dp, y = 12.dp)
                )
            }

            // Battery widget (top-right)
            if (osdSettings.showBattery) {
                BatteryWidget(
                    voltageMillivolts = viewerState.batteryVoltage,
                    avgVoltageMillivolts = viewerState.batteryAvgVoltage,
                    percent = viewerState.batteryPercent,
                    currentMilliamps = viewerState.batteryCurrent,
                    warning = viewerState.batteryWarning,
                    showIcon = osdSettings.showBatteryIcon,
                    showVoltage = osdSettings.showBatteryVoltage,
                    showCellVoltage = osdSettings.showBatteryCellVoltage,
                    showPercent = osdSettings.showBatteryPercent,
                    showCurrent = osdSettings.showBatteryCurrent,
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .offset(x = (-12).dp, y = 12.dp)
                )
            }

            // Pipeline timer (bottom-right)
            if (osdSettings.showPipelineTimer) {
                PipelineTimer(
                    startTimeMs = pipelineStartTime,
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .offset(x = (-12).dp, y = (-12).dp)
                )
            }

            // FPS counter (bottom-left)
            if (osdSettings.showFps) {
                FpsCounter(
                    fps = fps,
                    modifier = Modifier
                        .align(Alignment.BottomStart)
                        .offset(x = 12.dp, y = (-12).dp)
                )
            }

            // Recording indicator (bottom-right, offset left if timer is showing)
            if (viewerState.isRecording) {
                RecordingIndicator(
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .offset(
                            x = if (osdSettings.showPipelineTimer) {
                                (-140).dp
                            } else {
                                (-12).dp
                            },
                            y = (-12).dp
                        )
                )
            }
        }

        // Control overlay (hidden in spectator mode)
        if (!spectatorMode) {
            when {
                isMotionMode -> {
                    // Calibration overlay shown until first Zero press
                    if (motionController?.needsZero == true) {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .background(Color.Black.copy(alpha = 0.7f)),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = stringResource(R.string.motion_zero_overlay),
                                color = Color.White,
                                fontSize = 18.sp,
                                textAlign = TextAlign.Center,
                                modifier = Modifier
                                    .padding(horizontal = 48.dp)
                                    .background(
                                        Color.DarkGray.copy(alpha = 0.8f),
                                        RoundedCornerShape(12.dp)
                                    )
                                    .padding(24.dp)
                            )
                        }
                    }

                    // Motion control buttons (bottom-left, stacked)
                    Column(
                        modifier = Modifier
                            .align(Alignment.BottomStart)
                            .offset(x = 16.dp, y = (-16).dp)
                    ) {
                        // Pause/Resume button
                        Button(
                            onClick = { controlState.paused = !controlState.paused },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (controlState.paused)
                                    Color.Red.copy(alpha = 0.5f)
                                else
                                    Color.White.copy(alpha = 0.3f),
                                contentColor = Color.White
                            )
                        ) {
                            Text(
                                stringResource(
                                    if (controlState.paused) R.string.btn_resume
                                    else R.string.btn_pause
                                )
                            )
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        // Zero button for motion control calibration
                        Button(
                            onClick = { motionController?.zero() },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Color.White.copy(alpha = 0.3f),
                                contentColor = Color.White
                            )
                        ) {
                            Text(stringResource(R.string.btn_zero))
                        }
                    }
                }
                isGamepadMode -> {
                    // No overlay needed - input comes from the external controller
                }
                else -> {
                    TouchControls(
                        controlState = controlState,
                        modifier = Modifier.fillMaxSize(),
                        steeringInvert = touchSteeringInvert,
                        throttleInvert = touchThrottleInvert
                    )
                }
            }
        }
    }
}
