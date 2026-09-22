package com.rubinlabs.ispotify.data

data class Track(
    val id: String,
    val title: String,
    val artist: String,
    val sourceUrl: String,
    val artworkUrl: String = "",
    val durationSeconds: Long = 0,
    val localPath: String? = null,
)

data class ResolvedAudio(
    val url: String,
    val extension: String,
    val mimeType: String,
)
