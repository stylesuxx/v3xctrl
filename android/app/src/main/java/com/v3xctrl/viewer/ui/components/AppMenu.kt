package com.v3xctrl.viewer.ui.components

import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.v3xctrl.viewer.R

@Composable
fun AppMenu(
    expanded: Boolean,
    onDismiss: () -> Unit,
    onNavigateToNetwork: () -> Unit,
    onNavigateToFrequencies: () -> Unit,
    onNavigateToOSD: () -> Unit,
    onNavigateToControl: () -> Unit = {}
) {
    DropdownMenu(
        expanded = expanded,
        onDismissRequest = onDismiss
    ) {
        DropdownMenuItem(
            text = { Text(stringResource(R.string.menu_network)) },
            onClick = {
                onDismiss()
                onNavigateToNetwork()
            }
        )
        DropdownMenuItem(
            text = { Text(stringResource(R.string.menu_control)) },
            onClick = {
                onDismiss()
                onNavigateToControl()
            }
        )
        DropdownMenuItem(
            text = { Text(stringResource(R.string.menu_frequencies)) },
            onClick = {
                onDismiss()
                onNavigateToFrequencies()
            }
        )
        DropdownMenuItem(
            text = { Text(stringResource(R.string.menu_osd)) },
            onClick = {
                onDismiss()
                onNavigateToOSD()
            }
        )
    }
}
