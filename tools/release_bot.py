#!/usr/bin/env python3
"""Prepare iSpotify releases and synchronize published package metadata."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, value: str) -> None:
    (ROOT / path).write_text(value, encoding="utf-8", newline="\n")


def replace(path: str, pattern: str, replacement: str, count: int = 0) -> None:
    value = read(path)
    updated, matches = re.subn(pattern, replacement, value, count=count)
    if matches == 0:
        raise RuntimeError(f"Expected release pattern was not found in {path}")
    write(path, updated)


def current_version() -> str:
    match = re.search(r'APP_VERSION = "([^"]+)"', read("core/version.py"))
    if not match or not VERSION_RE.fullmatch(match.group(1)):
        raise RuntimeError("core/version.py does not contain a valid APP_VERSION")
    return match.group(1)


def bump_version(version: str, bump: str) -> str:
    match = VERSION_RE.fullmatch(version)
    if not match:
        raise ValueError(f"Invalid semantic version: {version}")
    major, minor, patch = map(int, match.groups())
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unsupported release bump: {bump}")


def set_release_version(version: str) -> None:
    major, minor, patch = map(int, version.split("."))
    replace(
        "core/version.py",
        r'APP_VERSION = "[^"]+"',
        f'APP_VERSION = "{version}"',
        count=1,
    )
    replace(
        "packaging/windows-installer.iss",
        r'#define AppVersion "[^"]+"',
        f'#define AppVersion "{version}"',
        count=1,
    )
    replace(
        "packaging/windows-version.txt",
        r"filevers=\(\d+, \d+, \d+, 0\)",
        f"filevers=({major}, {minor}, {patch}, 0)",
        count=1,
    )
    replace(
        "packaging/windows-version.txt",
        r"prodvers=\(\d+, \d+, \d+, 0\)",
        f"prodvers=({major}, {minor}, {patch}, 0)",
        count=1,
    )
    replace(
        "packaging/windows-version.txt",
        r"StringStruct\('FileVersion', '[^']+'\)",
        f"StringStruct('FileVersion', '{version}')",
        count=1,
    )
    replace(
        "packaging/windows-version.txt",
        r"StringStruct\('ProductVersion', '[^']+'\)",
        f"StringStruct('ProductVersion', '{version}')",
        count=1,
    )
    for path in ("packaging/arch/PKGBUILD", "packaging/aur/PKGBUILD"):
        replace(path, r"(?m)^pkgver=.*$", f"pkgver={version}", count=1)
    replace(
        "packaging/arch/PKGBUILD",
        r"(?s)(sha256sums=\(\s*)'[^']+'",
        r"\1'SKIP'",
        count=1,
    )
    replace(
        "packaging/aur/PKGBUILD",
        r"sha256sums=\('[^']+'\)",
        "sha256sums=('SKIP')",
        count=1,
    )
    replace(
        "README.md",
        r"The current stable release is \*\*v[^*]+\*\*",
        f"The current stable release is **v{version}**",
        count=1,
    )
    replace(
        "README.md",
        r"ispotify_\d+\.\d+\.\d+_amd64\.deb",
        f"ispotify_{version}_amd64.deb",
    )
    replace(
        "README.md",
        r"releases/download/v\d+\.\d+\.\d+/ispotify_",
        f"releases/download/v{version}/ispotify_",
        count=1,
    )


def release_notes(version: str, title: str, number: int, url: str, body: str) -> str:
    useful: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if lowered.startswith(("## validation", "## checklist")):
            break
        if line.startswith("- ") and len(line) <= 240:
            useful.append(line)
        if len(useful) == 8:
            break
    details = "\n".join(useful) if useful else f"- {title}"
    return (
        f"## iSpotify {version}\n\n"
        f"This release was prepared automatically after [PR #{number}]({url}) "
        "passed the protected test suite and merged.\n\n"
        f"### Changes\n\n{details}\n\n"
        "### Downloads\n\n"
        "- Windows installer: `ISpotify-Setup-x86_64.exe`\n"
        "- Windows portable: `ISpotify-windows-x86_64.exe`\n"
        "- Linux portable: `ISpotify-linux-x86_64`\n"
        f"- Debian/Ubuntu: `ispotify_{version}_amd64.deb`\n\n"
        "The release is published only after both platform builds succeed.\n"
    )


def prepare(args: argparse.Namespace) -> None:
    version = bump_version(current_version(), args.bump)
    set_release_version(version)
    notes_dir = ROOT / ".github" / "release-notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    notes = release_notes(version, args.title, args.number, args.url, args.body)
    (notes_dir / f"v{version}.md").write_text(notes, encoding="utf-8", newline="\n")
    print(version)


def sync(args: argparse.Namespace) -> None:
    version = args.version.removeprefix("v")
    if not VERSION_RE.fullmatch(version):
        raise ValueError(f"Invalid release version: {args.version}")
    replace(
        "packaging/arch/PKGBUILD",
        r"(?s)(sha256sums=\(\s*)'[^']+'",
        rf"\1'{args.linux_sha.lower()}'",
        count=1,
    )
    replace(
        "packaging/aur/PKGBUILD",
        r"sha256sums=\('[^']+'\)",
        f"sha256sums=('{args.source_sha.lower()}')",
        count=1,
    )
    for path in (
        "packaging/winget/ISpotify.ISpotify.yaml",
        "packaging/winget/ISpotify.ISpotify.installer.yaml",
        "packaging/winget/ISpotify.ISpotify.locale.en-US.yaml",
    ):
        replace(path, r"(?m)^PackageVersion: .+$", f"PackageVersion: {version}", count=1)
    replace(
        "packaging/winget/ISpotify.ISpotify.installer.yaml",
        r"releases/download/v\d+\.\d+\.\d+/ISpotify-Setup-x86_64\.exe",
        f"releases/download/v{version}/ISpotify-Setup-x86_64.exe",
        count=1,
    )
    replace(
        "packaging/winget/ISpotify.ISpotify.installer.yaml",
        r"(?m)^\s*InstallerSha256: .+$",
        f"    InstallerSha256: {args.installer_sha.upper()}",
        count=1,
    )
    replace(
        "packaging/winget/ISpotify.ISpotify.installer.yaml",
        r"iSpotify version \d+\.\d+\.\d+",
        f"iSpotify version {version}",
        count=1,
    )
    replace(
        "packaging/winget/ISpotify.ISpotify.installer.yaml",
        r"(?m)^\s*DisplayVersion: .+$",
        f"        DisplayVersion: {version}",
        count=1,
    )
    replace(
        "packaging/winget/ISpotify.ISpotify.locale.en-US.yaml",
        r"releases/tag/v\d+\.\d+\.\d+",
        f"releases/tag/v{version}",
        count=1,
    )
    notes = read(f".github/release-notes/v{version}.md")
    bullets = [line[2:] for line in notes.splitlines() if line.startswith("- ")][:3]
    if bullets:
        rendered = "ReleaseNotes: |-\n" + "\n".join(f"  {line}" for line in bullets)
        replace(
            "packaging/winget/ISpotify.ISpotify.locale.en-US.yaml",
            r"(?s)ReleaseNotes: \|-\n.*?\nReleaseNotesUrl:",
            rendered + "\nReleaseNotesUrl:",
            count=1,
        )


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser()
    subcommands = command.add_subparsers(dest="command", required=True)
    prepare_parser = subcommands.add_parser("prepare")
    prepare_parser.add_argument("--bump", choices=("major", "minor", "patch"), required=True)
    prepare_parser.add_argument("--title", required=True)
    prepare_parser.add_argument("--body", default="")
    prepare_parser.add_argument("--number", type=int, required=True)
    prepare_parser.add_argument("--url", required=True)
    prepare_parser.set_defaults(handler=prepare)
    sync_parser = subcommands.add_parser("sync")
    sync_parser.add_argument("--version", required=True)
    sync_parser.add_argument("--linux-sha", required=True)
    sync_parser.add_argument("--installer-sha", required=True)
    sync_parser.add_argument("--source-sha", required=True)
    sync_parser.set_defaults(handler=sync)
    return command


def main() -> None:
    args = parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
