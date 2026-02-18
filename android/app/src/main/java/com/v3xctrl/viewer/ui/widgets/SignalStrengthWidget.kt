package com.v3xctrl.viewer.ui.widgets

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.pow

private val SignalGreen = Color(0xFF00FF00)
private val SignalYellow = Color(0xFFFFFF00)
private val SignalOrange = Color(0xFFFFA500)
private val SignalRed = Color(0xFFFF0000)
private val SignalGrey = Color(0xFF888888)

private const val BAR_COUNT = 5

/**
 * Convert raw RSRP value to dBm.
 * Raw range 0-255, where 0 = -140 dBm and 255 = no signal.
 */
private fun rsrpToDbm(value: Int): Int = if (value == 255) -140 else value - 140

/**
 * Convert raw RSRQ value to dBm (x10 for integer math).
 * Raw range 0-40, formula: (value - 40) / 2
 * Returns null for value 255 (no data).
 */
private fun rsrqToDbmTenths(value: Int): Int? =
    if (value == 255) null else (value - 40) * 5 // multiply by 5 = divide by 2 then *10

/**
 * Map RSRP dBm to number of bars (0-5).
 * >= -80 dBm: 5 bars, >= -90: 4, >= -100: 3, >= -110: 2, >= -120: 1, else: 0
 */
private fun getBars(rsrpRaw: Int): Int {
    val dbm = rsrpToDbm(rsrpRaw)
    return when {
        dbm >= -80 -> 5
        dbm >= -90 -> 4
        dbm >= -100 -> 3
        dbm >= -110 -> 2
        dbm >= -120 -> 1
        else -> 0
    }
}

/**
 * Signal quality enum.
 * Based on RSRQ dBm: >= -9: EXCELLENT, >= -14: GOOD, >= -19: FAIR, else: POOR
 */
private enum class SignalQuality(val color: Color) {
    EXCELLENT(SignalGreen),
    GOOD(SignalYellow),
    FAIR(SignalOrange),
    POOR(SignalRed)
}

private fun getQuality(rsrqRaw: Int): SignalQuality {
    val dbmTenths = rsrqToDbmTenths(rsrqRaw) ?: return SignalQuality.POOR
    return when {
        dbmTenths >= -90 -> SignalQuality.EXCELLENT
        dbmTenths >= -140 -> SignalQuality.GOOD
        dbmTenths >= -190 -> SignalQuality.FAIR
        else -> SignalQuality.POOR
    }
}

/**
 * Signal strength OSD widget for landscape mode.
 * Shows a 5-bar signal icon with quality-colored background, plus optional band and cell ID text.
 */
@Composable
fun SignalStrengthWidget(
    rsrp: Int?,
    rsrq: Int?,
    band: String?,
    cellId: Int?,
    showIcon: Boolean = true,
    showBand: Boolean = false,
    showCellId: Boolean = false,
    modifier: Modifier = Modifier
) {
    val hasSignal = rsrp != null && rsrq != null &&
        rsrp != -1 && rsrp != 255 &&
        rsrq != -1 && rsrq != 255

    val hasText = (showBand && band != null) || (showCellId && cellId != null)
    if (!showIcon && !hasText) return

    OSDWidgetContainer(modifier = modifier) {
        Column(horizontalAlignment = Alignment.Start) {
            if (showIcon) {
                if (hasSignal) {
                    val bars = getBars(rsrp!!)
                    val quality = getQuality(rsrq!!)
                    Canvas(modifier = Modifier.size(width = 30.dp, height = 20.dp)) {
                        drawSignalBars(bars, quality.color)
                    }
                } else {
                    // No signal - draw X icon
                    Canvas(modifier = Modifier.size(width = 30.dp, height = 20.dp)) {
                        drawNoSignal()
                    }
                }
            }

            if (showBand) {
                val bandText = if (band != null && band != "?") "B$band" else "B?"
                Text(
                    text = bandText,
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp,
                    fontFamily = FontFamily.Monospace,
                    textAlign = TextAlign.Start
                )
            }

            if (showCellId && cellId != null) {
                val cellText = if (cellId > 0) {
                    val towerId = cellId shr 8
                    val sectionId = cellId and 0xFF
                    "$towerId:$sectionId"
                } else {
                    "CELL ?"
                }
                Text(
                    text = cellText,
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 13.sp,
                    fontFamily = FontFamily.Monospace,
                    textAlign = TextAlign.Start
                )
            }
        }
    }
}

/**
 * Draw 5-bar signal strength icon.
 * Uses non-linear height curve: ratio = ((i+1)/5)^1.4
 */
private fun DrawScope.drawSignalBars(filledBars: Int, qualityColor: Color) {
    val w = size.width
    val h = size.height
    val barSpacing = w * 0.05f
    val barWidth = (w - (BAR_COUNT - 1) * barSpacing) / BAR_COUNT
    val minBarHeight = h * 0.2f

    for (i in 0 until BAR_COUNT) {
        val ratio = ((i + 1).toFloat() / BAR_COUNT).pow(1.4f)
        val barHeight = minBarHeight + (h - minBarHeight) * ratio
        val barX = i * (barWidth + barSpacing)
        val barY = h - barHeight
        val color = if (i < filledBars) qualityColor else SignalGrey.copy(alpha = 0.5f)

        drawRect(
            color = color,
            topLeft = Offset(barX, barY),
            size = Size(barWidth, barHeight)
        )
    }
}

/**
 * Draw an X to indicate no signal data.
 */
private fun DrawScope.drawNoSignal() {
    val w = size.width
    val h = size.height
    val strokeWidth = 2.dp.toPx()

    // Draw grey bars in background
    drawSignalBars(0, SignalGrey)

    // Draw red X on top
    drawLine(
        color = SignalRed,
        start = Offset(0f, 0f),
        end = Offset(w, h),
        strokeWidth = strokeWidth
    )
    drawLine(
        color = SignalRed,
        start = Offset(w, 0f),
        end = Offset(0f, h),
        strokeWidth = strokeWidth
    )
}
