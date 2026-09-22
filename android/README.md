# iSpotify for Android

The Android client is a native Kotlin and Jetpack Compose application. Its
touch-first layout uses a pure-black Material 3 canvas, large artwork, pill
controls, persistent mini-player, and bottom navigation inspired by the visual
language of [Sakayori Music](https://github.com/Sakayorii/sakayori-music).
All iSpotify UI and application code in this directory is independently
implemented.

## Current features

- YouTube Music song search through NewPipe Extractor
- Streaming playback with AndroidX Media3
- Full-screen player and persistent mini-player
- Offline downloads into app-owned music storage
- Local offline library
- Home, Search, and Library navigation
- Android 8+ support, targeting Android 16

## Build

Install JDK 21 and the Android 16 SDK, then run:

```bash
cd android
./gradlew :app:assembleDebug
```

The APK is written to `app/build/outputs/apk/debug/app-debug.apk`. Every push
to the `android` branch also builds an installable preview APK in GitHub
Actions and publishes it to the `android-continuous` prerelease.

## Licensing

The Android client uses NewPipe Extractor, licensed under GPL-3.0-or-later.
Android distributions that include it must comply with that license. The
desktop application remains under the repository's MIT license.
