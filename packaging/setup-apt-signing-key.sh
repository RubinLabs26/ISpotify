#!/usr/bin/env bash
set -Eeuo pipefail

REPOSITORY="${REPOSITORY:-RubinLabs26/ISpotify}"
KEY_NAME="ISpotify APT Repository"
KEY_EMAIL="${KEY_EMAIL:-releases@rubinlabs26.github.io}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
KEY_HOME="$(mktemp -d)"
PRIVATE_KEY_FILE="$(mktemp)"

cleanup() {
  rm -f -- "$PRIVATE_KEY_FILE"
  rm -rf -- "$KEY_HOME"
}
trap cleanup EXIT
chmod 700 "$KEY_HOME"

command -v gpg >/dev/null 2>&1 || { echo "gpg is required." >&2; exit 1; }
command -v gh >/dev/null 2>&1 || { echo "GitHub CLI (gh) is required." >&2; exit 1; }
git -C "$ROOT_DIR" rev-parse --show-toplevel >/dev/null 2>&1 || {
  echo "Run this script from a checkout of ISpotify." >&2
  exit 1
}

echo "Generating a new signing key in a temporary keyring..."
GNUPGHOME="$KEY_HOME" gpg --batch --passphrase '' \
  --quick-generate-key "$KEY_NAME <$KEY_EMAIL>" rsa3072 sign 0

fingerprint="$(GNUPGHOME="$KEY_HOME" gpg --with-colons --list-secret-keys \
  | awk -F: '$1 == "fpr" { print $10; exit }')"
[[ "$fingerprint" =~ ^[A-F0-9]{40}$ ]] || {
  echo "Could not determine the generated key fingerprint." >&2
  exit 1
}

echo "Uploading the private key to GitHub Actions secret APT_REPOSITORY_PRIVATE_KEY..."
GNUPGHOME="$KEY_HOME" gpg --armor --export-secret-keys "$fingerprint" >"$PRIVATE_KEY_FILE"
gh secret set APT_REPOSITORY_PRIVATE_KEY --repo "$REPOSITORY" <"$PRIVATE_KEY_FILE"

echo "Updating the public key and installer fingerprint..."
GNUPGHOME="$KEY_HOME" gpg --armor --export "$fingerprint" >"$ROOT_DIR/packaging/apt/ispotify-archive-keyring.asc"
GNUPGHOME="$KEY_HOME" gpg --export "$fingerprint" >"$ROOT_DIR/packaging/apt/ispotify-archive-keyring.gpg"
sed -i -E "s/PACKAGE_KEY_FINGERPRINT=\"[A-Fa-f0-9]+\"/PACKAGE_KEY_FINGERPRINT=\"$fingerprint\"/" \
  "$ROOT_DIR/packaging/install-linux.sh"

echo
echo "Signing key configured for $REPOSITORY."
echo "Fingerprint: $fingerprint"
echo
echo "Review and commit these public files:"
echo "  packaging/apt/ispotify-archive-keyring.asc"
echo "  packaging/apt/ispotify-archive-keyring.gpg"
echo "  packaging/install-linux.sh"
echo
echo "The private key was uploaded to GitHub and removed from this machine's temporary files."
