package com.rubinlabs.ispotify.player

import android.app.Application
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import com.rubinlabs.ispotify.data.MusicRepository
import com.rubinlabs.ispotify.data.Track
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class AppTab { HOME, SEARCH, LIBRARY }

class ISpotifyViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = MusicRepository(application)
    val player = ExoPlayer.Builder(application).build()

    var selectedTab by mutableStateOf(AppTab.HOME)
    var query by mutableStateOf("")
    val searchResults = mutableStateListOf<Track>()
    val library = mutableStateListOf<Track>()
    var isSearching by mutableStateOf(false)
    var searchError by mutableStateOf<String?>(null)
    var currentTrack by mutableStateOf<Track?>(null)
    var playerExpanded by mutableStateOf(false)
    var isResolving by mutableStateOf(false)
    var isPlaying by mutableStateOf(false)
    var positionMs by mutableLongStateOf(0L)
    var durationMs by mutableLongStateOf(0L)
    var downloadProgress by mutableFloatStateOf(-1f)
    var message by mutableStateOf<String?>(null)
    private var playbackJob: Job? = null

    init {
        refreshLibrary()
        player.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(playing: Boolean) {
                isPlaying = playing
            }

            override fun onPlaybackStateChanged(state: Int) {
                durationMs = player.duration.coerceAtLeast(0L)
            }
        })
        viewModelScope.launch {
            while (true) {
                positionMs = player.currentPosition.coerceAtLeast(0L)
                durationMs = player.duration.coerceAtLeast(0L)
                delay(500)
            }
        }
    }

    fun search() {
        val text = query.trim()
        if (text.isEmpty()) return
        isSearching = true
        searchError = null
        viewModelScope.launch {
            runCatching { repository.search(text) }
                .onSuccess { tracks ->
                    searchResults.clear()
                    searchResults.addAll(tracks)
                    if (tracks.isEmpty()) searchError = "No songs found"
                }
                .onFailure { searchError = it.message ?: "Search failed" }
            isSearching = false
        }
    }

    fun play(track: Track) {
        playbackJob?.cancel()
        currentTrack = track
        playerExpanded = true
        isResolving = true
        message = null
        playbackJob = viewModelScope.launch {
            runCatching { repository.resolve(track) }
                .onSuccess { audio ->
                    val item = MediaItem.Builder()
                        .setUri(audio.url)
                        .setMediaId(track.id)
                        .setMediaMetadata(
                            MediaMetadata.Builder()
                                .setTitle(track.title)
                                .setArtist(track.artist)
                                .setArtworkUri(track.artworkUrl.takeIf(String::isNotBlank)?.let(Uri::parse))
                                .build(),
                        )
                        .build()
                    player.setMediaItem(item)
                    player.prepare()
                    player.play()
                }
                .onFailure { message = it.message ?: "Could not play this song" }
            isResolving = false
        }
    }

    fun togglePlayback() {
        if (player.isPlaying) player.pause() else player.play()
    }

    fun seekTo(value: Float) {
        if (durationMs > 0) player.seekTo((durationMs * value.coerceIn(0f, 1f)).toLong())
    }

    fun skip(offset: Int) {
        val active = if (selectedTab == AppTab.LIBRARY) library else searchResults
        val index = active.indexOfFirst { it.id == currentTrack?.id }
        if (active.isNotEmpty() && index >= 0) {
            play(active[(index + offset).coerceIn(0, active.lastIndex)])
        }
    }

    fun download(track: Track) {
        if (downloadProgress >= 0f) return
        downloadProgress = 0f
        message = "Downloading ${track.title}"
        viewModelScope.launch {
            runCatching {
                repository.download(track) { progress ->
                    viewModelScope.launch { downloadProgress = progress }
                }
            }.onSuccess {
                refreshLibrary()
                message = "Saved ${track.title} for offline playback"
            }.onFailure {
                message = it.message ?: "Download failed"
            }
            downloadProgress = -1f
        }
    }

    fun refreshLibrary() {
        viewModelScope.launch {
            val tracks = withContext(Dispatchers.IO) { repository.library() }
            library.clear()
            library.addAll(tracks)
        }
    }

    fun dismissMessage() {
        message = null
    }

    override fun onCleared() {
        player.release()
        super.onCleared()
    }
}
