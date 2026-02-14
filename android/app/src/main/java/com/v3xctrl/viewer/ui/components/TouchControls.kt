package com.v3xctrl.viewer.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.PointerId
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import com.v3xctrl.viewer.control.ControlState
import com.v3xctrl.viewer.input.applyDeadZone

/**
 * Touch control overlay for RC car control.
 * Left half: vertical drag for throttle (-1 to 1)
 * Right half: horizontal drag for steering (-1 to 1)
 * Supports multitouch - both controls can be used simultaneously.
 */
@Composable
fun TouchControls(
    controlState: ControlState,
    modifier: Modifier = Modifier,
    deadZone: Float = 0.1f,
    maxDragPx: Float = 200f
) {
    val density = LocalDensity.current
    val maxDrag = with(density) { maxDragPx.dp.toPx() }

    // Track active touches for each zone
    var leftTouch by remember { mutableStateOf<TouchInfo?>(null) }
    var rightTouch by remember { mutableStateOf<TouchInfo?>(null) }

    Box(
        modifier = modifier
            .fillMaxSize()
            .pointerInput(Unit) {
                awaitPointerEventScope {
                    while (true) {
                        val event = awaitPointerEvent()
                        val halfWidth = size.width / 2

                        // Process all pointer changes
                        event.changes.forEach { change ->
                            val isLeftSide = change.position.x < halfWidth

                            when {
                                // New touch down
                                change.pressed && change.previousPressed.not() -> {
                                    val touchInfo = TouchInfo(
                                        id = change.id,
                                        startPosition = change.position,
                                        currentPosition = change.position
                                    )

                                    if (isLeftSide && leftTouch == null) {
                                        leftTouch = touchInfo
                                    } else if (!isLeftSide && rightTouch == null) {
                                        rightTouch = touchInfo
                                    }
                                }

                                // Touch moved
                                change.pressed -> {
                                    when (change.id) {
                                        leftTouch?.id -> {
                                            leftTouch = leftTouch?.copy(currentPosition = change.position)
                                            leftTouch?.let { touch ->
                                                val deltaY = touch.startPosition.y - touch.currentPosition.y
                                                val normalized = (deltaY / maxDrag).coerceIn(-1f, 1f)
                                                controlState.throttle = applyDeadZone(normalized, deadZone)
                                            }
                                        }

                                        rightTouch?.id -> {
                                            rightTouch = rightTouch?.copy(currentPosition = change.position)
                                            rightTouch?.let { touch ->
                                                val deltaX = touch.currentPosition.x - touch.startPosition.x
                                                val normalized = (deltaX / maxDrag).coerceIn(-1f, 1f)
                                                controlState.steering = applyDeadZone(normalized, deadZone)
                                            }
                                        }
                                    }
                                }

                                // Touch released
                                !change.pressed && change.previousPressed -> {
                                    when (change.id) {
                                        leftTouch?.id -> {
                                            leftTouch = null
                                            controlState.throttle = 0f
                                        }

                                        rightTouch?.id -> {
                                            rightTouch = null
                                            controlState.steering = 0f
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
    ) {
        TouchIndicators(
            leftTouch = leftTouch,
            rightTouch = rightTouch,
            throttle = controlState.throttle,
            steering = controlState.steering
        )
    }
}

@Composable
private fun TouchIndicators(
    leftTouch: TouchInfo?,
    rightTouch: TouchInfo?,
    throttle: Float,
    steering: Float
) {
    val indicatorColor = Color.White.copy(alpha = 0.5f)
    val activeColor = Color.White.copy(alpha = 0.8f)

    Canvas(modifier = Modifier.fillMaxSize()) {
        val indicatorRadius = 60.dp.toPx()
        val innerRadius = 20.dp.toPx()

        // Draw left zone indicator (throttle)
        leftTouch?.let { touch ->
            // Outer circle at start position
            drawCircle(
                color = indicatorColor,
                radius = indicatorRadius,
                center = touch.startPosition,
                style = Stroke(width = 3.dp.toPx())
            )

            // Inner circle showing current position/value
            val offsetY = -throttle * (indicatorRadius - innerRadius)
            drawCircle(
                color = activeColor,
                radius = innerRadius,
                center = Offset(touch.startPosition.x, touch.startPosition.y + offsetY)
            )
        }

        // Draw right zone indicator (steering)
        rightTouch?.let { touch ->
            // Outer circle at start position
            drawCircle(
                color = indicatorColor,
                radius = indicatorRadius,
                center = touch.startPosition,
                style = Stroke(width = 3.dp.toPx())
            )

            // Inner circle showing current position/value
            val offsetX = steering * (indicatorRadius - innerRadius)
            drawCircle(
                color = activeColor,
                radius = innerRadius,
                center = Offset(touch.startPosition.x + offsetX, touch.startPosition.y)
            )
        }
    }
}

private data class TouchInfo(
    val id: PointerId,
    val startPosition: Offset,
    val currentPosition: Offset
)
