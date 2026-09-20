#!/usr/bin/env bash
set -Eeuo pipefail

REPOSITORY="itzlalpekhlua/ISpotify-Releases"
APP_NAME="iSpotify"
ASSET_NAME="ISpotify-linux-x86_64"
ICON_NAME="ispotify-logo.png"
MINIMUM_GLIBC="2.36"
MINIMUM_DISK_KB=307200

data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
bin_home="${XDG_BIN_HOME:-$HOME/.local/bin}"
app_dir="$data_home/ispotify"
application_dir="$data_home/applications"
icon_dir="$data_home/icons/hicolor/256x256/apps"
executable="$app_dir/ISpotify"
version_file="$app_dir/version"
launcher="$bin_home/ispotify"
desktop_file="$application_dir/ispotify.desktop"
icon_file="$icon_dir/ispotify.png"

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  reset=$'\033[0m'; bold=$'\033[1m'; dim=$'\033[2m'
  violet=$'\033[38;5;141m'; cyan=$'\033[38;5;45m'; green=$'\033[38;5;82m'
  yellow=$'\033[38;5;220m'; red=$'\033[38;5;203m'
else
  reset=""; bold=""; dim=""; violet=""; cyan=""; green=""; yellow=""; red=""
fi

banner() {
  printf '%s\n' "${violet}${bold}"
  printf '       _ ____              _   _  __       \n'
  printf '      (_) ___| _ __   ___ | |_(_)/ _|_   _ \n'
  printf "      | \___ \| '_ \ / _ \| __| | |_| | | |\n"
  printf '      | |___) | |_) | (_) | |_| |  _| |_| |\n'
  printf '      |_|____/| .__/ \___/ \__|_|_|  \__, |\n'
  printf '              |_|                    |___/ \n'
  printf '%s\n\n' "${reset}${dim}      Linux installer & compatibility checker${reset}"
}

section() { printf '\n%s%s%s\n' "$bold$cyan" "$1" "$reset"; }
pass() { printf '  %s✓%s %-18s %s\n' "$green" "$reset" "$1" "$2"; }
warn() { warnings=$((warnings + 1)); printf '  %s!%s %-18s %s\n' "$yellow" "$reset" "$1" "$2"; }
fail() { errors=$((errors + 1)); printf '  %s✗%s %-18s %s\n' "$red" "$reset" "$1" "$2"; }
info() { printf '  %s•%s %-18s %s\n' "$violet" "$reset" "$1" "$2"; }
step() { printf '%s%s→%s %s\n' "$bold" "$violet" "$reset" "$1"; }

usage() {
  cat <<EOF
Usage: install.sh [option]

  --check       Show compatibility and update status without changing anything
  --force       Reinstall even when the current version is installed
  --uninstall   Remove iSpotify from the current user account
  --help        Show this help

Set ISPOTIFY_VERSION to install a specific release, for example 17.0.0.
EOF
}

download() {
  local url="$1" destination="$2"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --silent --show-error "$url" --output "$destination"
  elif command -v wget >/dev/null 2>&1; then
    wget --quiet "$url" --output-document="$destination"
  else
    return 1
  fi
}

download_stdout() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --silent --show-error "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget --quiet "$url" --output-document=-
  else
    return 1
  fi
}

version_at_least() {
  local first
  first="$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n 1)"
  [[ "$first" == "$2" ]]
}

has_library() {
  local library="$1" linker="" cache=""
  if command -v ldconfig >/dev/null 2>&1; then
    linker="$(command -v ldconfig)"
  elif [[ -x /sbin/ldconfig ]]; then
    linker="/sbin/ldconfig"
  fi
  if [[ -n "$linker" ]]; then
    cache="$($linker -p 2>/dev/null || true)"
    [[ "$cache" == *"$library"* ]] && return 0
  fi
  find /lib /lib64 /usr/lib /usr/lib64 -maxdepth 4 -name "$library" -print -quit 2>/dev/null | grep -q .
}

dependency_hint() {
  if command -v pacman >/dev/null 2>&1; then
    printf '    %ssudo pacman -S --needed libglvnd libxkbcommon fontconfig libx11 libxcb xcb-util-cursor libpulse alsa-lib dbus%s\n' "$dim" "$reset"
  elif command -v apt-get >/dev/null 2>&1; then
    printf '    %ssudo apt-get install libgl1 libegl1 libxkbcommon0 libfontconfig1 libx11-6 libxcb1 libpulse0 dbus%s\n' "$dim" "$reset"
  elif command -v dnf >/dev/null 2>&1; then
    printf '    %ssudo dnf install mesa-libGL libxkbcommon fontconfig libX11 libxcb pulseaudio-libs dbus%s\n' "$dim" "$reset"
  fi
}

installed_version() {
  if [[ ! -x "$executable" ]]; then
    printf 'not installed'
  elif [[ -s "$version_file" ]]; then
    tr -d '\r\n' <"$version_file"
  else
    printf 'unknown (legacy installation)'
  fi
}

resolve_latest_version() {
  local metadata tag
  metadata="$(download_stdout "https://api.github.com/repos/$REPOSITORY/releases/latest" 2>/dev/null)" || return 1
  tag="$(printf '%s\n' "$metadata" | sed -n 's/^[[:space:]]*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
  [[ -n "$tag" ]] || return 1
  printf '%s' "${tag#v}"
}

system_summary() {
  local distro="Unknown Linux" desktop="${XDG_CURRENT_DESKTOP:-${DESKTOP_SESSION:-Not detected}}"
  local session="${XDG_SESSION_TYPE:-unknown}" memory_mb="unknown" cpu="unknown"
  if [[ -r /etc/os-release ]]; then
    distro="$(. /etc/os-release; printf '%s' "${PRETTY_NAME:-${NAME:-Linux}}")"
  fi
  [[ -r /proc/meminfo ]] && memory_mb="$(( $(awk '/MemTotal:/ {print $2}' /proc/meminfo) / 1024 )) MB"
  [[ -r /proc/cpuinfo ]] && cpu="$(awk -F: '/model name/ {sub(/^[ \t]+/, "", $2); print $2; exit}' /proc/cpuinfo)"

  section "System profile"
  info "Operating system" "$distro"
  info "Kernel" "$(uname -r)"
  info "Processor" "$cpu"
  info "Architecture" "$(uname -m)"
  info "Memory" "$memory_mb"
  info "Desktop" "$desktop ($session)"
}

compatibility_checks() {
  local os_name machine glibc="" disk_kb=0 memory_kb=0 missing_gui=0 library
  errors=0; warnings=0
  section "Compatibility checks"

  os_name="$(uname -s 2>/dev/null || true)"
  [[ "$os_name" == "Linux" ]] && pass "Operating system" "Linux" || fail "Operating system" "Linux is required"

  machine="$(uname -m 2>/dev/null || true)"
  case "$machine" in
    x86_64|amd64) pass "CPU architecture" "$machine supported" ;;
    *) fail "CPU architecture" "$machine is unsupported; x86_64 is required" ;;
  esac

  command -v getconf >/dev/null 2>&1 && glibc="$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}' || true)"
  if [[ -n "$glibc" ]] && version_at_least "$glibc" "$MINIMUM_GLIBC"; then
    pass "GNU libc" "$glibc (minimum $MINIMUM_GLIBC)"
  elif [[ -n "$glibc" ]]; then
    fail "GNU libc" "$glibc is too old; $MINIMUM_GLIBC or newer is required"
  else
    fail "GNU libc" "not detected; musl-only systems are unsupported"
  fi

  if command -v sha256sum >/dev/null 2>&1 && command -v install >/dev/null 2>&1; then
    pass "Core utilities" "sha256sum and install found"
  else
    fail "Core utilities" "sha256sum and install are required"
  fi

  if command -v curl >/dev/null 2>&1; then
    pass "Downloader" "curl"
  elif command -v wget >/dev/null 2>&1; then
    pass "Downloader" "wget"
  else
    fail "Downloader" "curl or wget is required"
  fi

  disk_kb="$(df -Pk "$HOME" 2>/dev/null | awk 'NR==2 {print $4}' || printf '0')"
  if [[ "$disk_kb" =~ ^[0-9]+$ ]] && (( disk_kb >= MINIMUM_DISK_KB )); then
    pass "Free disk space" "$((disk_kb / 1024)) MB available"
  else
    fail "Free disk space" "at least $((MINIMUM_DISK_KB / 1024)) MB is required"
  fi

  if [[ -r /proc/meminfo ]]; then
    memory_kb="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
    if (( memory_kb >= 1048576 )); then
      pass "System memory" "$((memory_kb / 1024)) MB"
    elif (( memory_kb >= 524288 )); then
      warn "System memory" "$((memory_kb / 1024)) MB; 1 GB or more is recommended"
    else
      fail "System memory" "$((memory_kb / 1024)) MB; at least 512 MB is required"
    fi
  else
    warn "System memory" "could not determine installed memory"
  fi

  for library in libGL.so.1 libEGL.so.1 libxkbcommon.so.0 libfontconfig.so.1 libX11.so.6 libxcb.so.1; do
    has_library "$library" || missing_gui=$((missing_gui + 1))
  done
  if (( missing_gui == 0 )); then
    pass "Desktop libraries" "Qt runtime dependencies found"
  else
    fail "Desktop libraries" "$missing_gui required libraries are missing"
    dependency_hint
  fi

  if has_library libpulse.so.0 || command -v wpctl >/dev/null 2>&1; then
    pass "Audio support" "PulseAudio or PipeWire support found"
  else
    warn "Audio support" "install PulseAudio or PipeWire for playback"
  fi

  if command -v deno >/dev/null 2>&1; then
    pass "JavaScript runtime" "Deno found"
  elif command -v node >/dev/null 2>&1; then
    pass "JavaScript runtime" "Node.js found"
  else
    warn "JavaScript runtime" "install Deno or Node.js for YouTube challenges"
  fi

  if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    pass "Graphical session" "display detected"
  else
    warn "Graphical session" "not detected in this terminal"
  fi
}

show_installation_status() {
  local current="$1" latest="$2"
  section "Installation status"
  [[ "$current" == "not installed" ]] && info "Installed version" "not installed" || pass "Installed version" "$current"
  if [[ -n "$latest" ]]; then
    info "Latest release" "$latest"
    if [[ "$current" == "$latest" ]]; then
      pass "Update status" "up to date"
    elif [[ "$current" != "not installed" ]]; then
      warn "Update status" "update available: $current → $latest"
    else
      info "Update status" "ready to install $latest"
    fi
  else
    warn "Latest release" "could not contact GitHub"
  fi
}

show_verdict() {
  section "Verdict"
  if (( errors == 0 )); then
    printf '  %s%s✓ SUPPORTED%s  This computer can run iSpotify.\n' "$bold" "$green" "$reset"
    (( warnings > 0 )) && printf '  %s%d advisory warning(s) shown above.%s\n' "$yellow" "$warnings" "$reset"
    return 0
  fi
  printf '  %s%s✗ NOT SUPPORTED YET%s  Fix %d required check(s) above.\n' "$bold" "$red" "$reset" "$errors"
  return 1
}

refresh_desktop() {
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$application_dir" >/dev/null 2>&1 || true
  command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "$data_home/icons/hicolor" >/dev/null 2>&1 || true
}

remove_installation() {
  banner
  step "Removing iSpotify from this user account"
  rm -f -- "$launcher" "$desktop_file" "$icon_file" "$executable" "$version_file"
  rmdir -- "$app_dir" 2>/dev/null || true
  refresh_desktop
  printf '%s%s✓ iSpotify was removed successfully.%s\n' "$bold" "$green" "$reset"
}

mode="install"; force_install=0
case "${1:-}" in
  "") ;;
  --check) mode="check" ;;
  --force) force_install=1 ;;
  --uninstall) remove_installation; exit 0 ;;
  --help|-h) usage; exit 0 ;;
  *) printf 'Unknown option: %s\n\n' "$1"; usage; exit 2 ;;
esac

banner
system_summary
compatibility_checks

current_version="$(installed_version)"
requested_version="${ISPOTIFY_VERSION:-latest}"
latest_version=""
if [[ "$requested_version" == "latest" ]]; then
  latest_version="$(resolve_latest_version || true)"
else
  latest_version="${requested_version#v}"
fi

show_installation_status "$current_version" "$latest_version"
show_verdict || exit 1

if [[ "$mode" == "check" ]]; then
  printf '\n%sNo changes were made.%s\n' "$dim" "$reset"
  exit 0
fi

if [[ -z "$latest_version" ]]; then
  printf '\n%sUnable to determine the release version. Check the network connection and try again.%s\n' "$red" "$reset"
  exit 1
fi

if [[ "$current_version" == "$latest_version" && "$force_install" -eq 0 ]]; then
  printf '\n%s%s✓ iSpotify %s is already up to date.%s\n' "$bold" "$green" "$latest_version" "$reset"
  exit 0
fi

tag="v$latest_version"
release_base="https://github.com/$REPOSITORY/releases/download/$tag"
temporary_dir="$(mktemp -d)"
trap 'rm -rf -- "$temporary_dir"' EXIT

printf '\n'
step "[1/5] Downloading iSpotify $latest_version"
download "$release_base/$ASSET_NAME" "$temporary_dir/$ASSET_NAME"
download "$release_base/$ASSET_NAME.sha256" "$temporary_dir/$ASSET_NAME.sha256"
download "$release_base/$ICON_NAME" "$temporary_dir/$ICON_NAME"

step "[2/5] Verifying SHA-256 checksum"
(
  cd "$temporary_dir"
  sha256sum --check --status "$ASSET_NAME.sha256"
) || { printf '%sChecksum verification failed. Nothing was installed.%s\n' "$red" "$reset"; exit 1; }

step "[3/5] Installing application files"
install -d -- "$app_dir" "$bin_home" "$application_dir" "$icon_dir"
install -m 755 -- "$temporary_dir/$ASSET_NAME" "$executable"
install -m 644 -- "$temporary_dir/$ICON_NAME" "$icon_file"
printf '%s\n' "$latest_version" >"$version_file"
ln -sfn -- "$executable" "$launcher"

step "[4/5] Registering desktop application"
cat >"$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=iSpotify
Comment=Search, play, and download music
Exec="$executable"
Icon=$icon_file
Terminal=false
Categories=AudioVideo;Audio;Player;
StartupNotify=true
EOF
chmod 644 "$desktop_file"
refresh_desktop

step "[5/5] Finishing setup"
printf '\n%s%s✓ iSpotify %s installed successfully.%s\n' "$bold" "$green" "$latest_version" "$reset"
printf '  Open it from the application menu or run: %s\n' "$launcher"
if [[ ":$PATH:" != *":$bin_home:"* ]]; then
  printf '  %sTip:%s add %s to PATH to run %sispotify%s directly.\n' "$yellow" "$reset" "$bin_home" "$bold" "$reset"
fi
