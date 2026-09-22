package com.rubinlabs.ispotify.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val ISpotifyColors = darkColorScheme(
    primary = Color(0xFFD2C4FF),
    onPrimary = Color(0xFF261947),
    primaryContainer = Color(0xFF37314E),
    onPrimaryContainer = Color(0xFFE9E0FF),
    secondary = Color(0xFFC9C3D7),
    background = Color.Black,
    onBackground = Color(0xFFF1EDF7),
    surface = Color(0xFF111114),
    onSurface = Color(0xFFF1EDF7),
    surfaceVariant = Color(0xFF202026),
    onSurfaceVariant = Color(0xFFCAC5D2),
    outline = Color(0xFF76717E),
    error = Color(0xFFFFB4AB),
)

@Composable
fun ISpotifyTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = ISpotifyColors,
        typography = Typography(),
        content = content,
    )
}
