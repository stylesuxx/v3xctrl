package com.v3xctrl.viewer.ui.widgets

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp

private val WarningOrange = Color(0xFFFFA500)

/**
 * Frame drop indicator widget.
 * Shows a warning triangle icon when UDP overrun (frame drops) is detected.
 */
@Composable
fun FrameDropIndicator(
    modifier: Modifier = Modifier
) {
    OSDWidgetContainer(
        modifier = modifier,
        padding = PaddingValues(6.dp),
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = Modifier.size(20.dp)) {
            val w = size.width
            val h = size.height
            val strokeWidth = 2.dp.toPx()

            // Warning triangle
            val trianglePath = Path().apply {
                moveTo(w / 2f, 0f)
                lineTo(w, h)
                lineTo(0f, h)
                close()
            }
            drawPath(
                path = trianglePath,
                color = WarningOrange,
                style = Stroke(
                    width = strokeWidth,
                    cap = StrokeCap.Round,
                    join = StrokeJoin.Round
                )
            )

            // Exclamation mark
            val centerX = w / 2f
            val dotRadius = 1.5.dp.toPx()

            // Line part
            drawLine(
                color = WarningOrange,
                start = Offset(centerX, h * 0.3f),
                end = Offset(centerX, h * 0.6f),
                strokeWidth = strokeWidth,
                cap = StrokeCap.Round
            )

            // Dot part
            drawCircle(
                color = WarningOrange,
                radius = dotRadius,
                center = Offset(centerX, h * 0.78f)
            )
        }
    }
}
