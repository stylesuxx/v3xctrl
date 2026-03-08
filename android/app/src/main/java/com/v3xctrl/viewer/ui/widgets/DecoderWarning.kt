package com.v3xctrl.viewer.ui.widgets

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.v3xctrl.viewer.GstViewer
import com.v3xctrl.viewer.R
import kotlinx.coroutines.delay

private val WarningRed = Color(0xCCCC0000)

@Composable
fun DecoderWarning(
  modifier: Modifier = Modifier
) {
  var showWarning by remember { mutableStateOf(false) }

  LaunchedEffect(Unit) {
    var consecutiveHigh = 0
    while (true) {
      val level = GstViewer.decodeQueueLevel
      if (level >= 2) {
        consecutiveHigh++
      } else {
        consecutiveHigh = 0
      }
      // Show warning after 3 consecutive polls with high queue level
      showWarning = consecutiveHigh >= 3
      delay(500)
    }
  }

  if (showWarning) {
    Text(
      text = stringResource(R.string.decoder_too_slow),
      color = Color.White,
      fontSize = 12.sp,
      textAlign = TextAlign.Center,
      modifier = modifier
        .fillMaxWidth()
        .background(WarningRed)
        .padding(vertical = 4.dp)
    )
  }
}
