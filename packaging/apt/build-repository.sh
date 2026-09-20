#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 4 ]]; then
  echo "Usage: $0 REPOSITORY_DIRECTORY DEB_FILE GNUPG_HOME PUBLIC_BASE_URL" >&2
  exit 2
fi

repository_directory="$(realpath -m "$1")"
deb_file="$(realpath "$2")"
gnupg_home="$(realpath "$3")"
public_base_url="${4%/}"

for command_name in dpkg-scanpackages apt-ftparchive gpg gzip; do
  command -v "$command_name" >/dev/null || { echo "$command_name is required" >&2; exit 1; }
done
[[ -f "$deb_file" ]] || { echo "Package not found: $deb_file" >&2; exit 1; }
[[ -d "$gnupg_home" ]] || { echo "GnuPG home not found: $gnupg_home" >&2; exit 1; }

package_name="$(basename "$deb_file")"
pool_directory="$repository_directory/pool/main/i/ispotify"
index_directory="$repository_directory/dists/stable/main/binary-amd64"
release_directory="$repository_directory/dists/stable"

mkdir -p "$pool_directory" "$index_directory"
install -m 644 "$deb_file" "$pool_directory/$package_name"

(
  cd "$repository_directory"
  dpkg-scanpackages --arch amd64 pool/main /dev/null >dists/stable/main/binary-amd64/Packages
  gzip -9nkf dists/stable/main/binary-amd64/Packages
)

cat >"$index_directory/Release" <<'EOF'
Archive: stable
Component: main
Origin: ISpotify
Label: ISpotify
Architecture: amd64
EOF

apt-ftparchive \
  -o APT::FTPArchive::Release::Origin=ISpotify \
  -o APT::FTPArchive::Release::Label=ISpotify \
  -o APT::FTPArchive::Release::Suite=stable \
  -o APT::FTPArchive::Release::Codename=stable \
  -o APT::FTPArchive::Release::Architectures=amd64 \
  -o APT::FTPArchive::Release::Components=main \
  -o APT::FTPArchive::Release::Description='ISpotify Linux packages' \
  release "$release_directory" >"$release_directory/Release"

gpg --homedir "$gnupg_home" --batch --yes --armor --detach-sign \
  --output "$release_directory/Release.gpg" "$release_directory/Release"
gpg --homedir "$gnupg_home" --batch --yes --armor --clearsign \
  --output "$release_directory/InRelease" "$release_directory/Release"
gpg --homedir "$gnupg_home" --batch --yes --export \
  --output "$repository_directory/ispotify-archive-keyring.gpg"
gpg --homedir "$gnupg_home" --batch --yes --armor --export \
  --output "$repository_directory/ispotify-archive-keyring.asc"

touch "$repository_directory/.nojekyll"
cat >"$repository_directory/index.html" <<EOF
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ISpotify APT Repository</title></head><body>
<h1>ISpotify APT Repository</h1>
<p>Signed packages for 64-bit Debian and Ubuntu systems with glibc 2.36 or newer.</p>
<pre>curl -fsSL $public_base_url/ispotify-archive-keyring.gpg | sudo tee /usr/share/keyrings/ispotify-archive-keyring.gpg &gt;/dev/null
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ispotify-archive-keyring.gpg] $public_base_url stable main" | sudo tee /etc/apt/sources.list.d/ispotify.list
sudo apt update
sudo apt install ispotify</pre>
</body></html>
EOF

echo "Repository generated at $repository_directory"
