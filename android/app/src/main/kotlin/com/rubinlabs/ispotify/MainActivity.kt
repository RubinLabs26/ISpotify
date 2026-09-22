package com.rubinlabs.ispotify

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.LibraryMusic
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import coil3.compose.AsyncImage
import com.rubinlabs.ispotify.data.Track
import com.rubinlabs.ispotify.player.AppTab
import com.rubinlabs.ispotify.player.ISpotifyViewModel
import com.rubinlabs.ispotify.ui.theme.ISpotifyTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            ISpotifyTheme { ISpotifyApp() }
        }
    }
}

@Composable
private fun ISpotifyApp(viewModel: ISpotifyViewModel = viewModel()) {
    val snackbar = remember { SnackbarHostState() }
    val message = viewModel.message
    LaunchedEffect(message) {
        if (message != null) {
            snackbar.showSnackbar(message)
            viewModel.dismissMessage()
        }
    }

    Surface(modifier = Modifier.fillMaxSize(), color = Color.Black) {
        if (viewModel.playerExpanded && viewModel.currentTrack != null) {
            PlayerScreen(viewModel)
        } else {
            Scaffold(
                containerColor = Color.Black,
                snackbarHost = { SnackbarHost(snackbar) },
                bottomBar = {
                    Column(modifier = Modifier.navigationBarsPadding()) {
                        viewModel.currentTrack?.let { track ->
                            MiniPlayer(track, viewModel)
                        }
                        AppNavigation(viewModel)
                    }
                },
            ) { padding ->
                when (viewModel.selectedTab) {
                    AppTab.HOME -> HomeScreen(viewModel, padding)
                    AppTab.SEARCH -> SearchScreen(viewModel, padding)
                    AppTab.LIBRARY -> LibraryScreen(viewModel, padding)
                }
            }
        }
    }
}

@Composable
private fun AppNavigation(viewModel: ISpotifyViewModel) {
    NavigationBar(containerColor = Color.Black, tonalElevation = 0.dp) {
        listOf(
            Triple(AppTab.HOME, Icons.Default.Home, "Home"),
            Triple(AppTab.SEARCH, Icons.Default.Search, "Search"),
            Triple(AppTab.LIBRARY, Icons.Default.LibraryMusic, "Library"),
        ).forEach { (tab, icon, label) ->
            NavigationBarItem(
                selected = viewModel.selectedTab == tab,
                onClick = {
                    viewModel.selectedTab = tab
                    if (tab == AppTab.LIBRARY) viewModel.refreshLibrary()
                },
                icon = { Icon(icon, contentDescription = label) },
                label = { Text(label) },
            )
        }
    }
}

@Composable
private fun PageTitle(title: String, subtitle: String? = null) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(horizontal = 22.dp, vertical = 18.dp),
    ) {
        Text(title, fontSize = 34.sp, fontWeight = FontWeight.SemiBold)
        subtitle?.let {
            Spacer(Modifier.height(4.dp))
            Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun HomeScreen(viewModel: ISpotifyViewModel, padding: PaddingValues) {
    val picks = (viewModel.library + viewModel.searchResults).distinctBy { it.id }.take(8)
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(bottom = padding.calculateBottomPadding()),
        contentPadding = PaddingValues(bottom = 28.dp),
    ) {
        item { PageTitle("Home", "Your music, ready when you are") }
        item {
            LazyRow(
                contentPadding = PaddingValues(horizontal = 22.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(listOf("Energize", "Focus", "Relax", "Feel good")) { mood ->
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        shape = RoundedCornerShape(24.dp),
                        modifier = Modifier.clickable {
                            viewModel.query = "$mood music"
                            viewModel.selectedTab = AppTab.SEARCH
                            viewModel.search()
                        },
                    ) {
                        Text(mood, modifier = Modifier.padding(horizontal = 20.dp, vertical = 11.dp))
                    }
                }
            }
        }
        item {
            SectionHeader("Quick picks", if (picks.isEmpty()) "Search to start listening" else "Play all") {
                if (picks.isNotEmpty()) viewModel.play(picks.first())
            }
        }
        if (picks.isEmpty()) {
            item {
                EmptyCard(
                    title = "Find your next song",
                    detail = "Search YouTube Music, stream instantly, then save tracks for offline playback.",
                    action = "Open search",
                ) { viewModel.selectedTab = AppTab.SEARCH }
            }
        } else {
            items(picks.take(4), key = { it.id }) { track ->
                TrackRow(track, viewModel)
            }
            item { SectionHeader("Keep listening") }
            item {
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 22.dp),
                    horizontalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    items(picks, key = { it.id }) { track ->
                        ArtworkCard(track) { viewModel.play(track) }
                    }
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(title: String, action: String? = null, onAction: () -> Unit = {}) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 22.dp, end = 22.dp, top = 30.dp, bottom = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            title,
            modifier = Modifier.weight(1f),
            fontSize = 25.sp,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary,
        )
        action?.let {
            OutlinedButton(onClick = onAction) { Text(it) }
        }
    }
}

@Composable
private fun EmptyCard(title: String, detail: String, action: String, onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .padding(horizontal = 22.dp)
            .fillMaxWidth(),
        color = MaterialTheme.colorScheme.surface,
        shape = RoundedCornerShape(24.dp),
    ) {
        Column(modifier = Modifier.padding(24.dp)) {
            Text(title, fontSize = 21.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            Text(detail, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(20.dp))
            Button(onClick = onClick) { Text(action) }
        }
    }
}

@Composable
private fun SearchScreen(viewModel: ISpotifyViewModel, padding: PaddingValues) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(bottom = padding.calculateBottomPadding()),
    ) {
        PageTitle("Search", "Songs from YouTube Music")
        OutlinedTextField(
            value = viewModel.query,
            onValueChange = { viewModel.query = it },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 22.dp),
            placeholder = { Text("Song, artist, or album") },
            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
            singleLine = true,
            shape = RoundedCornerShape(28.dp),
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { viewModel.search() }),
        )
        Spacer(Modifier.height(12.dp))
        when {
            viewModel.isSearching -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            viewModel.searchError != null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(viewModel.searchError.orEmpty(), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            else -> LazyColumn(contentPadding = PaddingValues(bottom = 24.dp)) {
                items(viewModel.searchResults, key = { it.id }) { track ->
                    TrackRow(track, viewModel)
                }
            }
        }
    }
}

@Composable
private fun LibraryScreen(viewModel: ISpotifyViewModel, padding: PaddingValues) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(bottom = padding.calculateBottomPadding()),
        contentPadding = PaddingValues(bottom = 24.dp),
    ) {
        item { PageTitle("Library", "Downloaded and available offline") }
        if (viewModel.library.isEmpty()) {
            item {
                EmptyCard(
                    title = "Your library is empty",
                    detail = "Download a song from Search and it will appear here.",
                    action = "Find music",
                ) { viewModel.selectedTab = AppTab.SEARCH }
            }
        } else {
            items(viewModel.library, key = { it.id }) { track -> TrackRow(track, viewModel) }
        }
    }
}

@Composable
private fun TrackRow(track: Track, viewModel: ISpotifyViewModel) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { viewModel.play(track) }
            .padding(horizontal = 22.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Artwork(track, 58.dp)
        Spacer(Modifier.width(14.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                track.title,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                fontWeight = FontWeight.SemiBold,
                fontSize = 16.sp,
            )
            Text(
                "${track.artist}  •  ${formatDuration(track.durationSeconds * 1000)}",
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        IconButton(onClick = { viewModel.download(track) }, enabled = track.localPath == null) {
            Icon(Icons.Default.Download, contentDescription = "Download ${track.title}")
        }
        IconButton(onClick = {}) {
            Icon(Icons.Default.MoreVert, contentDescription = "More options")
        }
    }
}

@Composable
private fun Artwork(track: Track, size: androidx.compose.ui.unit.Dp) {
    Surface(
        modifier = Modifier.size(size),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        if (track.artworkUrl.isNotBlank()) {
            AsyncImage(
                model = track.artworkUrl,
                contentDescription = null,
                contentScale = ContentScale.Crop,
            )
        } else {
            Box(contentAlignment = Alignment.Center) {
                Icon(Icons.Default.LibraryMusic, contentDescription = null)
            }
        }
    }
}

@Composable
private fun ArtworkCard(track: Track, onClick: () -> Unit) {
    Column(modifier = Modifier.width(154.dp).clickable(onClick = onClick)) {
        Artwork(track, 154.dp)
        Spacer(Modifier.height(9.dp))
        Text(track.title, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Bold)
        Text(
            track.artist,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun MiniPlayer(track: Track, viewModel: ISpotifyViewModel) {
    Surface(
        modifier = Modifier
            .padding(horizontal = 10.dp, vertical = 4.dp)
            .fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .clickable { viewModel.playerExpanded = true },
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column {
            Row(
                modifier = Modifier.padding(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Artwork(track, 48.dp)
                Spacer(Modifier.width(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(track.title, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Bold)
                    Text(track.artist, maxLines = 1, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                IconButton(onClick = viewModel::togglePlayback) {
                    Icon(
                        if (viewModel.isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow,
                        contentDescription = if (viewModel.isPlaying) "Pause" else "Play",
                    )
                }
            }
            if (viewModel.durationMs > 0) {
                LinearProgressIndicator(
                    progress = { (viewModel.positionMs.toFloat() / viewModel.durationMs).coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth().height(2.dp),
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PlayerScreen(viewModel: ISpotifyViewModel) {
    val track = viewModel.currentTrack ?: return
    Scaffold(
        containerColor = Color.Black,
        topBar = {
            TopAppBar(
                title = {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
                        Text("Now Playing", fontWeight = FontWeight.Bold)
                        Text("iSpotify", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp)
                    }
                },
                navigationIcon = {
                    IconButton(onClick = { viewModel.playerExpanded = false }) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = { Spacer(Modifier.width(48.dp)) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Black),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 28.dp)
                .navigationBarsPadding(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceEvenly,
        ) {
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(28.dp),
                color = MaterialTheme.colorScheme.surfaceVariant,
            ) {
                AsyncImage(
                    model = track.artworkUrl,
                    contentDescription = "Artwork for ${track.title}",
                    modifier = Modifier.fillMaxWidth().height(340.dp),
                    contentScale = ContentScale.Crop,
                )
            }

            Column(modifier = Modifier.fillMaxWidth()) {
                Text(track.title, fontSize = 28.sp, fontWeight = FontWeight.Bold, maxLines = 2)
                Text(track.artist, fontSize = 18.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(22.dp))
                androidx.compose.material3.Slider(
                    value = if (viewModel.durationMs > 0) {
                        (viewModel.positionMs.toFloat() / viewModel.durationMs).coerceIn(0f, 1f)
                    } else 0f,
                    onValueChange = viewModel::seekTo,
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text(formatDuration(viewModel.positionMs))
                    Text(formatDuration(viewModel.durationMs))
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                FilledIconButton(
                    onClick = { viewModel.skip(-1) },
                    modifier = Modifier.size(68.dp),
                    colors = IconButtonDefaults.filledIconButtonColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant,
                    ),
                ) { Icon(Icons.Default.SkipPrevious, contentDescription = "Previous", modifier = Modifier.size(30.dp)) }
                Button(
                    onClick = viewModel::togglePlayback,
                    modifier = Modifier.weight(1f).height(72.dp),
                    shape = RoundedCornerShape(36.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.onBackground,
                        contentColor = Color.Black,
                    ),
                ) {
                    if (viewModel.isResolving) {
                        CircularProgressIndicator(modifier = Modifier.size(26.dp), strokeWidth = 3.dp)
                    } else {
                        Icon(
                            if (viewModel.isPlaying) Icons.Default.Pause else Icons.Default.PlayArrow,
                            contentDescription = null,
                            modifier = Modifier.size(30.dp),
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(if (viewModel.isPlaying) "Pause" else "Play", fontSize = 18.sp)
                    }
                }
                FilledIconButton(
                    onClick = { viewModel.skip(1) },
                    modifier = Modifier.size(68.dp),
                    colors = IconButtonDefaults.filledIconButtonColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant,
                    ),
                ) { Icon(Icons.Default.SkipNext, contentDescription = "Next", modifier = Modifier.size(30.dp)) }
            }

            if (viewModel.downloadProgress >= 0f) {
                Column(Modifier.fillMaxWidth()) {
                    Text("Downloading… ${(viewModel.downloadProgress * 100).toInt()}%")
                    LinearProgressIndicator(
                        progress = { viewModel.downloadProgress.coerceIn(0f, 1f) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            } else {
                Button(
                    onClick = { viewModel.download(track) },
                    enabled = track.localPath == null,
                    shape = CircleShape,
                ) {
                    Icon(Icons.Default.Download, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (track.localPath == null) "Download" else "Available offline")
                }
            }
        }
    }
}

private fun formatDuration(milliseconds: Long): String {
    val seconds = (milliseconds / 1000).coerceAtLeast(0)
    return "%d:%02d".format(seconds / 60, seconds % 60)
}
