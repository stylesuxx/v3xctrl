package com.v3xctrl.viewer.ui.widgets

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/**
 * Shared container for OSD widgets.
 * Provides the standard semi-transparent black background with rounded corners.
 */
@Composable
fun OSDWidgetContainer(
    modifier: Modifier = Modifier,
    padding: PaddingValues = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
    contentAlignment: Alignment = Alignment.TopStart,
    content: @Composable BoxScope.() -> Unit
) {
    Box(
        modifier = modifier
            .background(
                color = Color.Black.copy(alpha = 0.6f),
                shape = RoundedCornerShape(5.dp)
            )
            .padding(padding),
        contentAlignment = contentAlignment,
        content = content
    )
}
