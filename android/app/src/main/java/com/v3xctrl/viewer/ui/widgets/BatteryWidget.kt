package com.v3xctrl.viewer.ui.widgets

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val BatteryRed = Color(0xFFFF0000)
private val BatteryOrange = Color(0xFFFFA500)
private val BatteryYellow = Color(0xFFFFFF00)
private val BatteryGreen = Color(0xFF00FF00)

/**
 * Returns the battery color based on percentage, matching the Python thresholds:
 * 0-10%: Red, 10-40%: Orange, 40-70%: Yellow, 70-100%: Green
 */
private fun batteryColor(percent: Int): Color = when {
    percent > 70 -> BatteryGreen
    percent > 40 -> BatteryYellow
    percent > 10 -> BatteryOrange
    else -> BatteryRed
}

/**
 * Battery OSD widget for landscape mode.
 * Shows a battery icon with fill level, total voltage, cell voltage, percentage, and current.
 * Each element can be individually toggled via the show* parameters.
 */
@Composable
fun BatteryWidget(
    voltageMillivolts: Int?,
    avgVoltageMillivolts: Int?,
    percent: Int?,
    currentMilliamps: Int?,
    warning: Boolean,
    showIcon: Boolean = true,
    showVoltage: Boolean = true,
    showCellVoltage: Boolean = true,
    showPercent: Boolean = true,
    showCurrent: Boolean = true,
    modifier: Modifier = Modifier
) {
    if (voltageMillivolts == null && percent == null) return

    val pct = (percent ?: 0).coerceIn(0, 100)
    val iconColor = batteryColor(pct)
    val textColor = if (warning) BatteryRed else Color.White

    val hasText = (showVoltage && voltageMillivolts != null) ||
        (showCellVoltage && avgVoltageMillivolts != null) ||
        (showPercent && percent != null) ||
        (showCurrent && currentMilliamps != null)

    if (!showIcon && !hasText) return

    Box(
        modifier = modifier
            .background(
                color = Color.Black.copy(alpha = 0.6f),
                shape = RoundedCornerShape(5.dp)
            )
            .padding(horizontal = 8.dp, vertical = 6.dp)
    ) {
        Column(horizontalAlignment = Alignment.End) {
            // Battery icon on top
            if (showIcon) {
                Canvas(modifier = Modifier.size(width = 36.dp, height = 20.dp)) {
                    val w = size.width
                    val h = size.height
                    val tipWidth = w * 0.08f
                    val bodyWidth = w - tipWidth
                    val cornerRadius = CornerRadius(3.dp.toPx(), 3.dp.toPx())
                    val strokeWidth = 1.5.dp.toPx()

                    // Battery body outline
                    drawRoundRect(
                        color = iconColor,
                        topLeft = Offset.Zero,
                        size = Size(bodyWidth, h),
                        cornerRadius = cornerRadius,
                        style = Stroke(width = strokeWidth)
                    )

                    // Battery tip (positive terminal)
                    val tipHeight = h * 0.4f
                    val tipY = (h - tipHeight) / 2
                    drawRoundRect(
                        color = iconColor,
                        topLeft = Offset(bodyWidth, tipY),
                        size = Size(tipWidth, tipHeight),
                        cornerRadius = CornerRadius(1.dp.toPx(), 1.dp.toPx())
                    )

                    // Fill level
                    val inset = strokeWidth + 2.dp.toPx()
                    val fillWidth = (bodyWidth - inset * 2) * (pct / 100f)
                    if (fillWidth > 0) {
                        drawRoundRect(
                            color = iconColor,
                            topLeft = Offset(inset, inset),
                            size = Size(fillWidth, h - inset * 2),
                            cornerRadius = CornerRadius(1.5.dp.toPx(), 1.5.dp.toPx())
                        )
                    }
                }
            }

            // Text values below icon
            if (showVoltage && voltageMillivolts != null) {
                Text(
                    text = "%.2fV".format(voltageMillivolts / 1000.0),
                    color = textColor,
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp,
                    fontFamily = FontFamily.Monospace,
                    textAlign = TextAlign.End
                )
            }

            if (showCellVoltage && avgVoltageMillivolts != null) {
                Text(
                    text = "%.2fV".format(avgVoltageMillivolts / 1000.0),
                    color = textColor,
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp,
                    fontFamily = FontFamily.Monospace,
                    textAlign = TextAlign.End
                )
            }

            if (showPercent && percent != null) {
                Text(
                    text = "${percent}%",
                    color = textColor,
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp,
                    fontFamily = FontFamily.Monospace,
                    textAlign = TextAlign.End
                )
            }

            if (showCurrent && currentMilliamps != null) {
                val currentText = if (currentMilliamps >= 1000) {
                    "%.2fA".format(currentMilliamps / 1000.0)
                } else {
                    "${currentMilliamps}mA"
                }
                Text(
                    text = currentText,
                    color = textColor,
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp,
                    fontFamily = FontFamily.Monospace,
                    textAlign = TextAlign.End
                )
            }
        }
    }
}
