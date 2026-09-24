# Repository and release bot

The repository bot manages pull requests and stable desktop releases with
GitHub Actions. It never checks out contributor code in its privileged pull
request workflow.

## Pull requests

Every pull request receives one release-impact label:

- `release:major` for breaking changes
- `release:minor` for features
- `release:patch` for fixes, maintenance, and dependency updates
- `release:skip` for documentation and release-metadata-only changes

Team pull requests are enrolled in GitHub auto-merge. Outside contributors
require a maintainer to add `automerge`. Dependabot patch and minor updates use
the `automerge` label from `.github/dependabot.yml`. Branch protection still
requires the `python` check and resolved conversations before merging.
When an eligible branch is stale, the bot requests GitHub's safe branch update
before enabling auto-merge; it never force-pushes or bypasses protection.

## Stable releases

After an ordinary pull request merges, the bot:

1. Bumps the semantic version according to its `release:*` label.
2. Updates app, Windows, Linux, Arch, AUR, README, and release-note metadata.
3. Opens a `bot:release` pull request and enables protected auto-merge.
4. Creates a draft GitHub release and pushes its tag after that PR merges.
5. Waits for the tagged Windows and Linux workflows to succeed.
6. Verifies the required installer, portable, and Debian assets.
7. Publishes the draft as the latest stable release.
8. Opens and auto-merges a `bot:metadata` PR with final Arch, AUR, and WinGet
   checksums.

If either platform build fails, the release stays draft. Re-running the failed
workflow lets the finalizer try again.

Maintainers can start a release manually from **Actions → Release bot → Run
workflow** and choose a patch, minor, or major bump.

## Required repository setting

The `RELEASE_BOT_TOKEN` Actions secret contains a maintainer token so events
created by the bot can trigger protected workflows. GitHub's normal
`GITHUB_TOKEN` intentionally suppresses many recursive workflow events.

The `APT_REPOSITORY_PRIVATE_KEY` Actions secret contains the armored private
key used only by tagged Linux builds to sign the APT repository metadata.
Tagged releases publish the matching `Release`, `Packages.gz`, and keyring
assets; the installer checks these assets before selecting repository mode.
