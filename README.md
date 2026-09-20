# iSpotify

iSpotify is a Rubin Labs desktop music app for searching YouTube, exploring
playlists, downloading audio, and managing a local library. It runs directly
on Windows and Linux without an iSpotify account, server, analytics, or
telemetry.

## Install

Download the Windows installer or portable app from
[Releases](https://github.com/RubinLabs26/ISpotify/releases).

On Linux, run the universal installer:

```bash
curl -fsSL https://raw.githubusercontent.com/RubinLabs26/ISpotify/main/packaging/install-linux.sh | bash
```

The script checks compatibility, detects the package manager, and offers the
signed APT or pacman repository where supported. Other compatible glibc
distributions receive the portable user installation. It installs aria2 for fast,
resumable downloads with live progress and speed. Partial files remain in
`~/.cache/ispotify/downloads` until installation succeeds.

Useful options are `--check`, `--repo`, `--standalone`, `--force`, `--yes`,
and `--uninstall`. The standalone Linux build requires x86-64 and glibc 2.36
or newer.

## Features

- Responsive song and playlist search
- Queued MP3 downloads and offline playback
- Live headphone detection with automatic pause when headphones disconnect
- Optional Discord status showing Listening to iSpotify and the current track
- Local library and playlist management
- Optional local YouTube cookies for sign-in checks
- Polished PySide6 interface for Windows and Linux

## Run from source

Python 3.10 or newer is required.

```bash
git clone https://github.com/RubinLabs26/ISpotify.git
cd ISpotify
python -m venv .venv
python -m pip install -r requirements.txt
python main.py
```

FFmpeg is used from `PATH` when available; `imageio-ffmpeg` provides a
fallback. Deno or Node.js is recommended for YouTube JavaScript challenges.

Cookies and downloaded audio stay in the operating system's user-data
directory. Treat exported cookies as private session credentials.

Discord Rich Presence can use the Discord desktop app already signed in on the
computer. Browser-based Discord users can instead choose **Connect Discord
account** in Settings and authorize iSpotify through Discord's official login
screen. Turn on **Show listening activity** to publish the current track.

OAuth credentials are stored in the operating system's credential vault when
one is available. iSpotify never requests or stores a Discord password, bot
token, or raw user token. The bundled Discord Social SDK runtime is version
1.10.19337; its third-party notices are included with every package.

Discord licenses its Social SDK runtime for distribution only when integrated
into an application, so the raw proprietary library is intentionally absent
from this public source repository. Official release packages include it.
Source checkouts continue to run without the library, with Discord account
login unavailable until an authorized SDK runtime is supplied locally.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
iSpotify is available under the [MIT License](LICENSE).

GitHub Actions checks and builds Windows and Linux packages after relevant code
changes. Every change on `main` updates the `continuous` prerelease, while a
matching `v*` tag publishes a stable versioned release.
