package com.v3xctrl.viewer.ui.screens

import android.view.SurfaceView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.v3xctrl.viewer.R
import com.v3xctrl.viewer.control.ControlState
import com.v3xctrl.viewer.control.ViewerState
import com.v3xctrl.viewer.input.MotionController
import com.v3xctrl.viewer.ui.components.TouchControls
import com.v3xctrl.viewer.ui.widgets.PipelineTimer
import com.v3xctrl.viewer.ui.widgets.RecordingIndicator

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
    showPipelineTimer: Boolean,
    pipelineStartTime: Long,
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

        // Pipeline timer (bottom-right)
        if (showPipelineTimer) {
            PipelineTimer(
                startTimeMs = pipelineStartTime,
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .offset(x = (-12).dp, y = (-12).dp)
            )
        }

        // Recording indicator (bottom-right, offset left if timer is showing)
        if (viewerState.isRecording) {
            RecordingIndicator(
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .offset(
                        x = if (showPipelineTimer) (-140).dp else (-12).dp,
                        y = (-12).dp
                    )
            )
        }

        // Control overlay (hidden in spectator mode)
        if (!spectatorMode) {
            when {
                isMotionMode -> {
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
                        modifier = Modifier.fillMaxSize()
                    )
                }
            }
        }
    }
}
