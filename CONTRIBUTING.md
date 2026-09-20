# Contributing to iSpotify

Thank you for helping improve iSpotify. Contributions should preserve the
playlist workflow, responsive interface, local-only architecture, and
cross-platform behavior while keeping setup reproducible.

## Before you start

Open an issue before a large change so the intended behavior and scope can be agreed on. Small fixes and documentation improvements can go directly to a pull request.

Do not commit credentials, cookies, downloaded media, runtime binaries, build
output, logs, or user library data. The application must not add telemetry or
send user data through a project-operated server. Only contribute code and
assets that you have the right to distribute.

## Development workflow

1. Fork or clone the repository and create a branch from `main`.
2. Keep each change focused on one problem.
3. Match the existing Python style: four-space indentation, clear names, and small functions.
4. Preserve background search and download behavior, atomic library writes, managed queues, and safe multimedia source switching.
5. Add or update documentation when behavior, dependencies, or setup requirements change.
6. Run the relevant checks locally and describe them in the pull request.

## Current priorities

- Add focused tests for library migration, search parsing, playlist pagination, and download queues.
- Improve accessibility and keyboard navigation.
- Keep network work away from the UI thread and bound any new caches.
- Improve playlist organization and library filtering.
- Keep Windows, Debian, Arch Linux, and portable builds reproducible.
- Improve local yt-dlp reliability and actionable error reporting.

Run `python -m compileall -q main.py core ui` and launch the app before opening a pull request. Exercise each page affected by the change.

## Pull requests

A pull request should explain:

- The problem it solves
- The resulting behavior
- How it was tested
- Any remaining limitation or compatibility concern

Keep unrelated formatting or refactoring out of functional changes. Never weaken integrity checks or error handling merely to make setup appear successful.

## Reporting bugs

Include the operating system, Python version, steps to reproduce, expected result, actual result, and a short relevant log excerpt. Remove usernames, local paths, tokens, and personal library data before posting logs.

By contributing, you agree that your contribution is licensed under the repository's [MIT License](LICENSE).
