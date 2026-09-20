# iSpotify

iSpotify is a desktop music application built with Python and PySide6. It can
search YouTube, inspect playlists, download audio for offline playback, and
manage a local library through a focused dark interface.

The application runs locally. Searches and downloads connect directly to
YouTube; there is no iSpotify server, account, analytics service, or telemetry.

## Features

- Song and playlist search without blocking the interface
- Paged playlist browsing and queued downloads
- Local MP3 library and integrated playback
- Windows and Linux desktop support
- Optional YouTube cookies for sign-in and bot-check errors
- Local storage under the operating system's user data directory

## Install a release

Windows users can download either the installer or the portable executable
from [Releases](https://github.com/itzlalpekhlua/ISpotify-Releases/releases).

Linux users can run the compatibility-aware installer:

```bash
curl -fsSL https://raw.githubusercontent.com/RubinLabs26/ISpotify/main/packaging/install-linux.sh | bash
```

The installer checks the CPU architecture, Linux distribution, glibc version,
desktop integration tools, free disk space, and any existing iSpotify version
before it changes the system. Run the checker by itself with:

```bash
curl -fsSL https://raw.githubusercontent.com/RubinLabs26/ISpotify/main/packaging/install-linux.sh | bash -s -- --check
```

The standalone Linux executable targets x86-64 distributions with glibc 2.36
or newer, including current Debian, Ubuntu, Fedora, and Arch Linux releases.

### Debian and Ubuntu APT repository

```bash
curl -fsSL https://github.com/itzlalpekhlua/ISpotify-Releases/releases/latest/download/ispotify-archive-keyring.gpg \
  | sudo tee /usr/share/keyrings/ispotify-archive-keyring.gpg >/dev/null
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ispotify-archive-keyring.gpg] https://github.com/itzlalpekhlua/ISpotify-Releases/releases/latest/download ./" \
  | sudo tee /etc/apt/sources.list.d/ispotify.list
sudo apt update
sudo apt install ispotify
```

### Arch Linux repository

```bash
curl -fsSL https://github.com/itzlalpekhlua/ISpotify-Releases/releases/latest/download/ispotify-archive-keyring.asc \
  -o /tmp/ispotify-archive-keyring.asc
sudo pacman-key --add /tmp/ispotify-archive-keyring.asc
sudo pacman-key --lsign-key FBF50CE755A06C567BFAE4D81C9D795EC0272267
printf '\n[ispotify]\nSigLevel = Required DatabaseOptional\nServer = https://github.com/itzlalpekhlua/ISpotify-Releases/releases/latest/download\n' \
  | sudo tee -a /etc/pacman.conf
sudo pacman -Syu ispotify
rm /tmp/ispotify-archive-keyring.asc
```

## Run from source

Python 3.10 or newer is required. FFmpeg from the system `PATH` is preferred;
`imageio-ffmpeg` provides a bundled fallback. Current yt-dlp versions also
benefit from Deno 2.3 or newer for YouTube JavaScript challenges.

```bash
git clone https://github.com/RubinLabs26/ISpotify.git
cd ISpotify
python -m venv .venv
```

On Linux or macOS:

```bash
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

## Cookies for YouTube checks

YouTube can sometimes return a sign-in wall or a "confirm you're not a robot"
response. When this happens:

1. Open a private browser window and sign in to YouTube.
2. In the same tab, open `https://www.youtube.com/robots.txt`.
3. Export the `youtube.com` cookies as a JSON array or Netscape `cookies.txt`.
4. Open **Settings** in iSpotify, paste the complete export, and choose
   **Test & save cookies**.

iSpotify validates the session before replacing an existing cookie set. The
cookies remain on the computer and are sent only to the Google and YouTube
services used for search and media access. They are session credentials, so do
not post them in issues, logs, or chat messages.

## Local storage

On Linux, iSpotify follows XDG paths:

- Audio: `${XDG_DATA_HOME:-$HOME/.local/share}/ishpoitfy/downloads`
- Library: `${XDG_DATA_HOME:-$HOME/.local/share}/ishpoitfy/library.json`
- Cookies: `${XDG_DATA_HOME:-$HOME/.local/share}/ishpoitfy/cookies.txt`
- Cache: `${XDG_CACHE_HOME:-$HOME/.cache}/ishpoitfy`

The equivalent directories are resolved from the current user's home on
Windows. An older checkout with `library.json` or `downloads/` beside
`main.py` is migrated by copying those files into user storage.

## Development

Run the checks before opening a pull request:

```bash
python -m compileall -q main.py core ui tests
python -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance and
[SECURITY.md](SECURITY.md) for private vulnerability reporting.

## License

iSpotify is available under the [MIT License](LICENSE).
