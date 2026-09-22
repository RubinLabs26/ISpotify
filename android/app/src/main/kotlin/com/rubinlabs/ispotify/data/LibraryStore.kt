package com.rubinlabs.ispotify.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

class LibraryStore(context: Context) {
    private val preferences = context.getSharedPreferences("library", Context.MODE_PRIVATE)

    fun load(): List<Track> {
        val raw = preferences.getString("tracks", "[]") ?: "[]"
        return runCatching {
            val array = JSONArray(raw)
            buildList {
                repeat(array.length()) { index ->
                    val item = array.getJSONObject(index)
                    add(
                        Track(
                            id = item.getString("id"),
                            title = item.getString("title"),
                            artist = item.optString("artist", "Unknown artist"),
                            sourceUrl = item.getString("sourceUrl"),
                            artworkUrl = item.optString("artworkUrl"),
                            durationSeconds = item.optLong("durationSeconds"),
                            localPath = item.optString("localPath").takeIf(String::isNotBlank),
                        ),
                    )
                }
            }
        }.getOrDefault(emptyList())
    }

    fun add(track: Track) {
        val tracks = load().filterNot { it.id == track.id }.toMutableList()
        tracks.add(0, track)
        val array = JSONArray()
        tracks.forEach { song ->
            array.put(
                JSONObject()
                    .put("id", song.id)
                    .put("title", song.title)
                    .put("artist", song.artist)
                    .put("sourceUrl", song.sourceUrl)
                    .put("artworkUrl", song.artworkUrl)
                    .put("durationSeconds", song.durationSeconds)
                    .put("localPath", song.localPath.orEmpty()),
            )
        }
        preferences.edit().putString("tracks", array.toString()).apply()
    }
}
