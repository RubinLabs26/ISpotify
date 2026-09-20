#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 OUTPUT_DIRECTORY DEB_FILE GNUPG_HOME" >&2
  exit 2
fi

output_directory="$(realpath -m "$1")"
deb_file="$(realpath "$2")"
gnupg_home="$(realpath "$3")"

for command_name in dpkg-scanpackages apt-ftparchive gpg gzip; do
  command -v "$command_name" >/dev/null || {
    echo "$command_name is required" >&2
    exit 1
  }
done
[[ -f "$deb_file" ]] || { echo "Package not found: $deb_file" >&2; exit 1; }
[[ -d "$gnupg_home" ]] || { echo "GnuPG home not found: $gnupg_home" >&2; exit 1; }

mkdir -p "$output_directory"
install -m 644 "$deb_file" "$output_directory/$(basename "$deb_file")"

(
  cd "$output_directory"
  dpkg-scanpackages --arch amd64 . /dev/null >Packages
  sed -i 's|^Filename: ./|Filename: |' Packages
  gzip -9nkf Packages

  apt-ftparchive \
    -o APT::FTPArchive::Release::Origin=ISpotify \
    -o APT::FTPArchive::Release::Label=ISpotify \
    -o APT::FTPArchive::Release::Suite=stable \
    -o APT::FTPArchive::Release::Codename=stable \
    -o APT::FTPArchive::Release::Architectures=amd64 \
    -o APT::FTPArchive::Release::Description='ISpotify Linux packages' \
    release . >Release

  gpg --homedir "$gnupg_home" --batch --yes --armor --detach-sign \
    --output Release.gpg Release
  gpg --homedir "$gnupg_home" --batch --yes --armor --clearsign \
    --output InRelease Release
  gpg --homedir "$gnupg_home" --batch --yes --export \
    --output ispotify-archive-keyring.gpg
  gpg --homedir "$gnupg_home" --batch --yes --armor --export \
    --output ispotify-archive-keyring.asc
)

echo "Flat signed repository generated at $output_directory"
