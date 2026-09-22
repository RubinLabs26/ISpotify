package com.rubinlabs.ispotify.data

import android.content.Context
import android.os.Environment
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.ServiceList
import org.schabi.newpipe.extractor.services.youtube.linkHandler.YoutubeSearchQueryHandlerFactory.MUSIC_SONGS
import org.schabi.newpipe.extractor.stream.StreamInfo
import org.schabi.newpipe.extractor.stream.StreamInfoItem
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean

class MusicRepository(private val context: Context) {
    private val initialized = AtomicBoolean(false)
    private val downloads = LibraryStore(context)
    private val downloadClient = OkHttpClient()

    private fun ensureExtractor() {
        if (initialized.compareAndSet(false, true)) {
            NewPipe.init(ExtractorDownloader())
        }
    }

    suspend fun search(query: String): List<Track> = withContext(Dispatchers.IO) {
        ensureExtractor()
        val extractor = ServiceList.YouTube.getSearchExtractor(
            query.trim(),
            listOf(MUSIC_SONGS),
            "",
        )
        extractor.fetchPage()
        extractor.initialPage.items
            .filterIsInstance<StreamInfoItem>()
            .filter { it.duration > 0 }
            .take(30)
            .map { item ->
                Track(
                    id = item.url,
                    title = item.name,
                    artist = item.uploaderName ?: "Unknown artist",
                    sourceUrl = item.url,
                    artworkUrl = item.thumbnails.maxByOrNull { image ->
                        image.width.coerceAtLeast(0) * image.height.coerceAtLeast(0)
                    }?.url.orEmpty(),
                    durationSeconds = item.duration,
                )
            }
    }

    suspend fun resolve(track: Track): ResolvedAudio = withContext(Dispatchers.IO) {
        track.localPath?.let { path ->
            val file = File(path)
            if (file.isFile) {
                return@withContext ResolvedAudio(file.toURI().toString(), file.extension, "audio/*")
            }
        }
        ensureExtractor()
        val info = StreamInfo.getInfo(track.sourceUrl)
        val audio = info.audioStreams
            .filter { it.isUrl }
            .maxByOrNull { it.averageBitrate }
            ?: error("No playable audio stream was found")
        val format = audio.format
        ResolvedAudio(
            url = audio.content,
            extension = format?.suffix ?: "m4a",
            mimeType = format?.mimeType ?: "audio/mp4",
        )
    }

    suspend fun download(track: Track, onProgress: (Float) -> Unit): Track =
        withContext(Dispatchers.IO) {
            val audio = resolve(track)
            val directory = File(
                context.getExternalFilesDir(Environment.DIRECTORY_MUSIC),
                "iSpotify",
            ).apply { mkdirs() }
            val safeName = track.title.replace(Regex("[^A-Za-z0-9._ -]"), "_").take(80)
            val target = File(directory, "$safeName.${audio.extension}")
            val partial = File(directory, "$safeName.${audio.extension}.part")
            val request = Request.Builder().url(audio.url).build()
            downloadClient.newCall(request).execute().use { response ->
                check(response.isSuccessful) { "Download failed with HTTP ${response.code}" }
                val body = checkNotNull(response.body)
                val total = body.contentLength()
                var copied = 0L
                body.byteStream().use { input ->
                    partial.outputStream().buffered().use { output ->
                        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            output.write(buffer, 0, count)
                            copied += count
                            if (total > 0) onProgress(copied.toFloat() / total)
                        }
                    }
                }
            }
            check(partial.renameTo(target)) { "Could not finish the downloaded file" }
            track.copy(localPath = target.absolutePath).also(downloads::add)
        }

    fun library(): List<Track> = downloads.load().filter { song ->
        song.localPath?.let(::File)?.isFile == true
    }
}
