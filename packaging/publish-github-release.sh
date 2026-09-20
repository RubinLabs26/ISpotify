#!/usr/bin/env bash
set -Eeuo pipefail

asset_directory="${1:-release}"

[[ -d "$asset_directory" ]] || {
  echo "Release asset directory not found: $asset_directory" >&2
  exit 1
}
: "${GH_TOKEN:?GH_TOKEN is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${GITHUB_SHA:?GITHUB_SHA is required}"
: "${GITHUB_REF:?GITHUB_REF is required}"

if [[ "$GITHUB_REF" == refs/tags/v* ]]; then
  release_tag="${GITHUB_REF#refs/tags/}"
  release_title="iSpotify ${release_tag#v}"
  release_kind="stable"
elif [[ "$GITHUB_REF" == "refs/heads/main" ]]; then
  release_tag="continuous"
  release_title="iSpotify Continuous Build"
  release_kind="continuous"
else
  echo "This ref does not publish a release: $GITHUB_REF"
  exit 0
fi

mapfile -d '' assets < <(find "$asset_directory" -maxdepth 1 -type f -print0)
(( ${#assets[@]} > 0 )) || {
  echo "No release assets found in $asset_directory" >&2
  exit 1
}

if [[ "$release_kind" == "continuous" ]]; then
  ref_endpoint="repos/$GITHUB_REPOSITORY/git/refs/tags/$release_tag"
  if gh api "repos/$GITHUB_REPOSITORY/git/ref/tags/$release_tag" >/dev/null 2>&1; then
    gh api --method PATCH "$ref_endpoint" -f sha="$GITHUB_SHA" -F force=true >/dev/null
  else
    gh api --method POST "repos/$GITHUB_REPOSITORY/git/refs" \
      -f ref="refs/tags/$release_tag" -f sha="$GITHUB_SHA" >/dev/null 2>&1 || \
      gh api --method PATCH "$ref_endpoint" -f sha="$GITHUB_SHA" -F force=true >/dev/null
  fi

  notes="Automatically built from the latest main branch commit. This prerelease may change after every source update."
  if ! gh release view "$release_tag" >/dev/null 2>&1; then
    gh release create "$release_tag" --title "$release_title" --prerelease \
      --latest=false --notes "$notes" >/dev/null 2>&1 || sleep 2
  fi
  gh release edit "$release_tag" --title "$release_title" --prerelease \
    --notes "$notes" >/dev/null
else
  gh release view "$release_tag" >/dev/null 2>&1 || { \
    gh release create "$release_tag" --title "$release_title" \
      --generate-notes >/dev/null 2>&1 || sleep 2; \
  }
  gh release view "$release_tag" >/dev/null
fi

gh release upload "$release_tag" "${assets[@]}" --clobber
echo "Published ${#assets[@]} asset(s) to $release_tag"
