#!/usr/bin/env bash
set -Eeuo pipefail

REPOSITORY="RubinLabs26/ISpotify"
REPOSITORY_URL="https://github.com/$REPOSITORY/releases/latest/download"
PACKAGE_KEY_FINGERPRINT="FBF50CE755A06C567BFAE4D81C9D795EC0272267"
APP_NAME="iSpotify"
ASSET_NAME="ISpotify-linux-x86_64"
ICON_NAME="ispotify-logo.png"
MINIMUM_GLIBC="2.36"
MINIMUM_DISK_KB=307200

data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
cache_home="${XDG_CACHE_HOME:-$HOME/.cache}"
bin_home="${XDG_BIN_HOME:-$HOME/.local/bin}"
app_dir="$data_home/ispotify"
application_dir="$data_home/applications"
icon_dir="$data_home/icons/hicolor/256x256/apps"
executable="$app_dir/ISpotify"
version_file="$app_dir/version"
launcher="$bin_home/ispotify"
desktop_file="$application_dir/ispotify.desktop"
icon_file="$icon_dir/ispotify.png"
download_cache="$cache_home/ispotify/downloads"

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
Usage: install.sh [options]

  --check       Show compatibility and update status without changing anything
  --force       Reinstall even when the current version is installed
  --repo        Add the signed APT or pacman repository and install from it
  --standalone  Install the portable application for the current user
  --yes         Accept the recommended repository option without prompting
  --uninstall   Remove iSpotify and its configured package repository
  --help        Show this help

Set ISPOTIFY_VERSION to install a specific release, for example 18.0.0.
Interrupted application downloads are resumed from ~/.cache/ispotify/downloads.
EOF
}

detect_package_manager() {
  local manager
  for manager in apt-get dnf yum pacman zypper apk xbps-install emerge; do
    command -v "$manager" >/dev/null 2>&1 && { printf '%s' "$manager"; return 0; }
  done
  return 1
}

run_as_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    printf '%saria2 needs administrator access, but sudo is not installed.%s\n' "$red" "$reset" >&2
    return 1
  fi
}

install_aria2() {
  local manager="$1"
  step "Installing aria2 with $manager"
  case "$manager" in
    apt-get)
      run_as_root apt-get update
      run_as_root apt-get install -y aria2
      ;;
    dnf) run_as_root dnf install -y aria2 ;;
    yum) run_as_root yum install -y aria2 ;;
    pacman) run_as_root pacman -Sy --needed --noconfirm aria2 ;;
    zypper) run_as_root zypper --non-interactive install aria2 ;;
    apk) run_as_root apk add aria2 ;;
    xbps-install) run_as_root xbps-install -Sy aria2 ;;
    emerge) run_as_root emerge --ask=n net-misc/aria2 ;;
    *) return 1 ;;
  esac
  command -v aria2c >/dev/null 2>&1
}

ensure_aria2() {
  local manager=""
  if command -v aria2c >/dev/null 2>&1; then
    pass "Download engine" "aria2 already installed"
    return 0
  fi
  manager="$(detect_package_manager || true)"
  if [[ -z "$manager" ]]; then
    printf '%sNo supported package manager was found to install aria2.%s\n' "$yellow" "$reset" >&2
    return 1
  fi
  install_aria2 "$manager"
}

choose_installation_method() {
  local manager reply=""
  manager="$(detect_package_manager || true)"

  if [[ "$installation_method" == "repo" ]]; then
    case "$manager" in
      apt-get|pacman) printf 'repo'; return 0 ;;
      *)
        printf '%sThe signed repository is available for APT and pacman systems; %s was detected.%s\n' \
          "$red" "${manager:-no package manager}" "$reset" >&2
        return 1
        ;;
    esac
  fi
  [[ "$installation_method" == "standalone" ]] && { printf 'standalone'; return 0; }

  case "$manager" in
    apt-get|pacman)
      if (( assume_yes )); then
        printf 'repo'
      elif [[ -r /dev/tty && -w /dev/tty ]]; then
        printf '\n%sAdd the signed iSpotify repository for automatic updates? [Y/n] %s' "$bold" "$reset" >/dev/tty
        IFS= read -r reply </dev/tty || true
        case "$reply" in
          n|N|no|NO|No) printf 'standalone' ;;
          *) printf 'repo' ;;
        esac
      else
        info "Install method" "no interactive terminal; using standalone mode" >&2
        printf 'standalone'
      fi
      ;;
    *)
      info "Install method" "portable user installation for ${manager:-this system}" >&2
      printf 'standalone'
      ;;
  esac
}

install_from_repository() {
  local manager="$1" setup_dir apt_source pacman_source
  if ! command -v curl >/dev/null 2>&1 && \
     ! command -v wget >/dev/null 2>&1 && \
     ! command -v aria2c >/dev/null 2>&1; then
    ensure_aria2
  fi
  setup_dir="$(mktemp -d)"
  repository_setup_dir="$setup_dir"
  trap '[[ -n "${repository_setup_dir:-}" ]] && rm -rf -- "$repository_setup_dir"' EXIT

  section "Signed package repository"
  case "$manager" in
    apt-get)
      step "Downloading the Rubin Labs package signing key"
      download "$REPOSITORY_URL/ispotify-archive-keyring.gpg" "$setup_dir/ispotify-archive-keyring.gpg"
      run_as_root install -Dm644 "$setup_dir/ispotify-archive-keyring.gpg" \
        /usr/share/keyrings/ispotify-archive-keyring.gpg
      apt_source="$setup_dir/ispotify.list"
      printf '%s\n' \
        "deb [arch=amd64 signed-by=/usr/share/keyrings/ispotify-archive-keyring.gpg] $REPOSITORY_URL ./" \
        >"$apt_source"
      run_as_root install -Dm644 "$apt_source" /etc/apt/sources.list.d/ispotify.list
      step "Refreshing APT and installing iSpotify"
      run_as_root apt-get update
      run_as_root apt-get install -y ispotify
      ;;
    pacman)
      step "Downloading the Rubin Labs package signing key"
      download "$REPOSITORY_URL/ispotify-archive-keyring.asc" "$setup_dir/ispotify-archive-keyring.asc"
      run_as_root pacman-key --init
      run_as_root pacman-key --add "$setup_dir/ispotify-archive-keyring.asc"
      run_as_root pacman-key --lsign-key "$PACKAGE_KEY_FINGERPRINT"
      if ! grep -Eq '^[[:space:]]*\[ispotify\][[:space:]]*$' /etc/pacman.conf; then
        pacman_source="$setup_dir/ispotify.conf"
        printf '\n[ispotify]\nSigLevel = Required DatabaseOptional\nServer = %s\n' "$REPOSITORY_URL" >"$pacman_source"
        run_as_root tee -a /etc/pacman.conf <"$pacman_source" >/dev/null
      fi
      step "Refreshing pacman and installing iSpotify"
      run_as_root pacman -Syu --needed --noconfirm ispotify
      ;;
    *) return 1 ;;
  esac

  rm -rf -- "$setup_dir"
  repository_setup_dir=""
  trap - EXIT
  printf '\n%s%s✓ iSpotify is installed and will update through %s.%s\n' \
    "$bold" "$green" "$manager" "$reset"
}

download() {
  local url="$1" destination="$2"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --silent --show-error "$url" --output "$destination"
  elif command -v wget >/dev/null 2>&1; then
    wget --quiet "$url" --output-document="$destination"
  elif command -v aria2c >/dev/null 2>&1; then
    aria2c --quiet=true --allow-overwrite=true --auto-file-renaming=false \
      --dir="$(dirname "$destination")" --out="$(basename "$destination")" "$url"
  else
    return 1
  fi
}

format_bytes() {
  awk -v value="${1:-0}" 'BEGIN {
    split("B KiB MiB GiB", units, " ")
    unit = 1
    while (value >= 1024 && unit < 4) {
      value /= 1024
      unit++
    }
    if (unit == 1) printf "%.0f %s", value, units[unit]
    else printf "%.1f %s", value, units[unit]
  }'
}

download_with_progress() {
  local url="$1" destination="$2" started finished elapsed size speed
  local partial="$destination.aria2"

  command -v aria2c >/dev/null 2>&1 || return 1
  install -d -- "$(dirname "$destination")"
  if [[ -s "$destination" || -s "$partial" ]]; then
    printf '  %sResuming cached download from %s%s\n' "$cyan" "$(dirname "$destination")" "$reset"
  else
    printf '  %sDownloading with 8 aria2 connections%s\n' "$bold" "$reset"
  fi

  started="$(date +%s)"
  aria2c \
    --continue=true \
    --max-connection-per-server=8 \
    --split=8 \
    --min-split-size=1M \
    --file-allocation=none \
    --allow-overwrite=true \
    --auto-file-renaming=false \
    --summary-interval=1 \
    --console-log-level=notice \
    --dir="$(dirname "$destination")" \
    --out="$(basename "$destination")" \
    "$url"
  finished="$(date +%s)"
  size="$(wc -c <"$destination")"
  elapsed=$((finished - started))
  (( elapsed > 0 )) || elapsed=1
  speed=$((size / elapsed))
  printf '  %s✓%s Downloaded %s in %d s — average %s/s\n' \
    "$green" "$reset" "$(format_bytes "$size")" "$elapsed" "$(format_bytes "$speed")"
}

download_stdout() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --silent --show-error "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget --quiet "$url" --output-document=-
  elif command -v aria2c >/dev/null 2>&1; then
    local temporary_file
    temporary_file="$(mktemp)"
    aria2c --quiet=true --allow-overwrite=true --auto-file-renaming=false \
      --dir="$(dirname "$temporary_file")" --out="$(basename "$temporary_file")" "$url" || {
        rm -f -- "$temporary_file"; return 1;
      }
    cat "$temporary_file"
    rm -f -- "$temporary_file"
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
  local version=""
  if command -v dpkg-query >/dev/null 2>&1 && \
     version="$(dpkg-query -W -f='${Version}' ispotify 2>/dev/null)" && [[ -n "$version" ]]; then
    printf '%s' "$version"
  elif command -v pacman >/dev/null 2>&1 && \
       version="$(pacman -Q ispotify 2>/dev/null | awk '{print $2}')" && [[ -n "$version" ]]; then
    printf '%s' "${version%-*}"
  elif [[ -x "$executable" && -s "$version_file" ]]; then
    tr -d '\r\n' <"$version_file"
  elif [[ -x "$executable" ]]; then
    printf 'unknown (legacy installation)'
  else
    printf 'not installed'
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
  local session="${XDG_SESSION_TYPE:-unknown}" memory_mb="unknown" cpu="unknown" manager=""
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
  manager="$(detect_package_manager || true)"
  info "Package manager" "${manager:-not detected}"
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

  if command -v aria2c >/dev/null 2>&1; then
    pass "Download engine" "aria2 with resume support"
  elif command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1; then
    warn "Download engine" "aria2 will be installed automatically"
  elif detect_package_manager >/dev/null 2>&1; then
    warn "Download engine" "aria2 will be installed before downloading"
  else
    fail "Download engine" "aria2 is missing and no supported package manager was found"
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
  local pacman_config=""
  banner
  step "Removing iSpotify and its package repository"
  if command -v dpkg-query >/dev/null 2>&1 && dpkg-query -W ispotify >/dev/null 2>&1; then
    run_as_root apt-get remove -y ispotify
    run_as_root rm -f -- /etc/apt/sources.list.d/ispotify.list \
      /usr/share/keyrings/ispotify-archive-keyring.gpg
  elif command -v pacman >/dev/null 2>&1 && pacman -Q ispotify >/dev/null 2>&1; then
    run_as_root pacman -Rns --noconfirm ispotify
    if grep -Eq '^[[:space:]]*\[ispotify\][[:space:]]*$' /etc/pacman.conf; then
      pacman_config="$(mktemp)"
      awk '
        BEGIN { skip = 0 }
        /^[[:space:]]*\[ispotify\][[:space:]]*$/ { skip = 1; next }
        skip && /^[[:space:]]*\[/ { skip = 0 }
        !skip { print }
      ' /etc/pacman.conf >"$pacman_config"
      run_as_root install -m 644 "$pacman_config" /etc/pacman.conf
      rm -f -- "$pacman_config"
    fi
  fi
  rm -f -- "$launcher" "$desktop_file" "$icon_file" "$executable" "$version_file"
  rmdir -- "$app_dir" 2>/dev/null || true
  refresh_desktop
  printf '%s%s✓ iSpotify was removed successfully.%s\n' "$bold" "$green" "$reset"
}

mode="install"; force_install=0; installation_method="auto"; assume_yes=0
while (( $# > 0 )); do
  case "$1" in
    --check) mode="check" ;;
    --force) force_install=1 ;;
    --repo) installation_method="repo" ;;
    --standalone) installation_method="standalone" ;;
    --yes|-y) assume_yes=1 ;;
    --uninstall) mode="uninstall" ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n\n' "$1"; usage; exit 2 ;;
  esac
  shift
done

if [[ "$mode" == "uninstall" ]]; then
  remove_installation
  exit 0
fi

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

selected_method="$(choose_installation_method)" || exit 1
if [[ "$selected_method" == "repo" ]]; then
  detected_manager="$(detect_package_manager)"
  install_from_repository "$detected_manager"
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

if ! ensure_aria2; then
  printf '\n%sUnable to install aria2 automatically. Install aria2 with your package manager and run this installer again.%s\n' "$red" "$reset"
  exit 1
fi

tag="v$latest_version"
release_base="https://github.com/$REPOSITORY/releases/download/$tag"
temporary_dir="$(mktemp -d)"
cached_release_dir="$download_cache/$tag"
trap 'rm -rf -- "$temporary_dir"' EXIT
install -d -- "$cached_release_dir"

printf '\n'
step "[1/5] Downloading iSpotify $latest_version"
download_with_progress "$release_base/$ASSET_NAME" "$cached_release_dir/$ASSET_NAME"
download "$release_base/$ASSET_NAME.sha256" "$cached_release_dir/$ASSET_NAME.sha256"
download "$release_base/$ICON_NAME" "$temporary_dir/$ICON_NAME"

step "[2/5] Verifying SHA-256 checksum"
(
  cd "$cached_release_dir"
  sha256sum --check --status "$ASSET_NAME.sha256"
) || {
  rm -f -- "$cached_release_dir/$ASSET_NAME" "$cached_release_dir/$ASSET_NAME.aria2" \
    "$cached_release_dir/$ASSET_NAME.sha256"
  printf '%sChecksum verification failed. The invalid download was removed and nothing was installed.%s\n' "$red" "$reset"
  exit 1
}

step "[3/5] Installing application files"
install -d -- "$app_dir" "$bin_home" "$application_dir" "$icon_dir"
install -m 755 -- "$cached_release_dir/$ASSET_NAME" "$executable"
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
rm -f -- "$cached_release_dir/$ASSET_NAME" "$cached_release_dir/$ASSET_NAME.aria2" \
  "$cached_release_dir/$ASSET_NAME.sha256"
rmdir -- "$cached_release_dir" 2>/dev/null || true
printf '\n%s%s✓ iSpotify %s installed successfully.%s\n' "$bold" "$green" "$latest_version" "$reset"
printf '  Open it from the application menu or run: %s\n' "$launcher"
if [[ ":$PATH:" != *":$bin_home:"* ]]; then
  printf '  %sTip:%s add %s to PATH to run %sispotify%s directly.\n' "$yellow" "$reset" "$bin_home" "$bold" "$reset"
fi
