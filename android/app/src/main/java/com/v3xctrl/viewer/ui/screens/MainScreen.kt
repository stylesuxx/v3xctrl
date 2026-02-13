package com.v3xctrl.viewer.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.v3xctrl.viewer.ConnectionState
import com.v3xctrl.viewer.R
import com.v3xctrl.viewer.ui.components.AppMenu
import com.v3xctrl.viewer.ui.theme.V3xctrlTheme
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    relayUrl: String,
    sessionId: String,
    connectionState: ConnectionState,
    onStartConnection: () -> Unit,
    onAbortConnection: () -> Unit,
    onClearError: () -> Unit,
    onNavigateToNetwork: () -> Unit = {},
    onNavigateToFrequencies: () -> Unit = {},
    onNavigateToOSD: () -> Unit = {},
    onNavigateToControl: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    var menuExpanded by remember { mutableStateOf(false) }
    val canStartViewer = relayUrl.isNotBlank() && sessionId.isNotBlank()
    val isConnecting = connectionState is ConnectionState.Connecting

    // Capture error message locally so it persists after connectionState resets
    var errorVisible by remember { mutableStateOf(false) }
    var displayedError by remember { mutableStateOf("") }

    // When an error arrives, capture it and reset connectionState to Idle
    LaunchedEffect(connectionState) {
        if (connectionState is ConnectionState.Error) {
            displayedError = connectionState.message
            errorVisible = true
            onClearError()
        }
    }

    // Auto-dismiss the error after 3 seconds
    LaunchedEffect(errorVisible) {
        if (errorVisible) {
            delay(3000)
            errorVisible = false
        }
    }

    Scaffold(
        modifier = modifier.fillMaxSize(),
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.app_name)) },
                actions = {
                    IconButton(
                        onClick = { menuExpanded = true },
                        enabled = !isConnecting
                    ) {
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
                }
            )
        }
    ) { innerPadding ->
        val context = LocalContext.current

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(top = 48.dp),
            verticalArrangement = Arrangement.Top,
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Image(
                painter = painterResource(R.drawable.v3xctrl_logo),
                contentDescription = stringResource(R.string.app_name),
                contentScale = ContentScale.Fit,
                modifier = Modifier
                    .fillMaxWidth(0.6f)
                    .aspectRatio(981.6f / 627.8f)
            )

            Spacer(modifier = Modifier.height(24.dp))

            Text(
                text = stringResource(R.string.app_description),
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(0.8f)
            )

            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = stringResource(R.string.app_link),
                style = MaterialTheme.typography.displaySmall.copy(
                    color = MaterialTheme.colorScheme.primary,
                    textDecoration = TextDecoration.Underline
                ),
                modifier = Modifier.clickable {
                    context.startActivity(
                        Intent(Intent.ACTION_VIEW, Uri.parse(context.getString(R.string.app_url)))
                    )
                }
            )

            Spacer(modifier = Modifier.height(24.dp))

            if (isConnecting) {
                CircularProgressIndicator()
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = stringResource(R.string.establishing_connection),
                    style = MaterialTheme.typography.bodyMedium
                )
                Spacer(modifier = Modifier.height(16.dp))
                OutlinedButton(
                    onClick = onAbortConnection,
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.error
                    ),
                    modifier = Modifier
                        .fillMaxWidth(0.7f)
                        .height(56.dp)
                ) {
                    Text(
                        stringResource(R.string.abort),
                        style = MaterialTheme.typography.titleLarge
                    )
                }
            } else {
                Button(
                    onClick = onStartConnection,
                    enabled = canStartViewer,
                    modifier = Modifier
                        .fillMaxWidth(0.7f)
                        .height(56.dp)
                ) {
                    Text(
                        stringResource(R.string.start_viewer),
                        style = MaterialTheme.typography.titleLarge
                    )
                }

                if (!canStartViewer) {
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = stringResource(R.string.configure_network_message),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }
            }

            AnimatedVisibility(
                visible = errorVisible,
                enter = fadeIn(),
                exit = fadeOut()
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = displayedError,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth(0.8f)
                    )
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun MainScreenPreview() {
    V3xctrlTheme {
        MainScreen(
            relayUrl = "",
            sessionId = "",
            connectionState = ConnectionState.Idle,
            onStartConnection = {},
            onAbortConnection = {},
            onClearError = {}
        )
    }
}

@Preview(showBackground = true)
@Composable
fun MainScreenConnectingPreview() {
    V3xctrlTheme {
        MainScreen(
            relayUrl = "relay.v3xctrl.com:8888",
            sessionId = "test-session",
            connectionState = ConnectionState.Connecting,
            onStartConnection = {},
            onAbortConnection = {},
            onClearError = {}
        )
    }
}
