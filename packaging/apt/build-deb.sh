#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 VERSION BINARY ICON [OUTPUT_DIRECTORY]" >&2
  exit 2
fi

version="$1"
binary="$(realpath "$2")"
icon="$(realpath "$3")"
output_directory="${4:-dist/debian}"

[[ "$version" =~ ^[0-9][0-9A-Za-z.+:~_-]*$ ]] || {
  echo "Invalid Debian package version: $version" >&2
  exit 2
}
[[ -x "$binary" ]] || { echo "Executable not found: $binary" >&2; exit 1; }
[[ -f "$icon" ]] || { echo "Icon not found: $icon" >&2; exit 1; }
command -v dpkg-deb >/dev/null || { echo "dpkg-deb is required" >&2; exit 1; }

work_directory="$(mktemp -d)"
trap 'rm -rf -- "$work_directory"' EXIT
package_root="$work_directory/ispotify_${version}_amd64"

install -d \
  "$package_root/DEBIAN" \
  "$package_root/opt/ispotify" \
  "$package_root/usr/bin" \
  "$package_root/usr/share/applications" \
  "$package_root/usr/share/icons/hicolor/256x256/apps" \
  "$package_root/usr/share/doc/ispotify"

install -m 755 "$binary" "$package_root/opt/ispotify/ISpotify"
install -m 644 "$icon" "$package_root/usr/share/icons/hicolor/256x256/apps/ispotify.png"
printf '%s\n' "$version" >"$package_root/opt/ispotify/version"
ln -s /opt/ispotify/ISpotify "$package_root/usr/bin/ispotify"

cat >"$package_root/usr/share/applications/ispotify.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Version=1.0
Name=iSpotify
Comment=Search, play, and download music
Exec=/usr/bin/ispotify
Icon=ispotify
Terminal=false
Categories=AudioVideo;Audio;Player;
StartupNotify=true
EOF

cat >"$package_root/usr/share/doc/ispotify/copyright" <<'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: iSpotify
Source: https://github.com/RubinLabs26/ISpotify

Files: *
Copyright: 2026 ISpotify contributors
License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included in all
 copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.
EOF

cat >"$package_root/usr/share/doc/ispotify/changelog" <<EOF
ispotify ($version) stable; urgency=medium

  * Publish the Windows and Linux desktop release.
  * Add the signed APT repository and desktop integration.

 -- ISpotify Releases <packages@ispotify.invalid>  $(date -R)
EOF
gzip -9n "$package_root/usr/share/doc/ispotify/changelog"

installed_size="$(du -sk "$package_root" | awk '{print $1}')"
cat >"$package_root/DEBIAN/control" <<EOF
Package: ispotify
Version: $version
Section: sound
Priority: optional
Architecture: amd64
Installed-Size: $installed_size
Maintainer: ISpotify Releases <packages@ispotify.invalid>
Depends: libc6 (>= 2.36), libgl1, libegl1, libxkbcommon0, libfontconfig1, libx11-6, libxcb1, libpulse0, dbus
Recommends: pipewire-pulse | pulseaudio
Homepage: https://github.com/RubinLabs26/ISpotify
Description: Desktop music search, playback, and download application
 iSpotify provides music search, playback, playlists, library management, and
 local audio downloads in a PySide6 desktop interface.
EOF

cat >"$package_root/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
EOF

cat >"$package_root/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
EOF
chmod 755 "$package_root/DEBIAN/postinst" "$package_root/DEBIAN/postrm"

mkdir -p "$output_directory"
output="$(realpath "$output_directory")/ispotify_${version}_amd64.deb"
dpkg-deb --root-owner-group --build "$package_root" "$output"
sha256sum "$output"
