"""Idempotently create the minimal Lumi Labs Discord server layout."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from discord_bot_config import bot_token, config

API = "https://discord.com/api/v10"

CATEGORY = "✦・Lumi Labs"
CHANNELS = {
    "👋・welcome": "Start here for Lumi Labs and iSpotify updates.",
    "📢・announcements": "Official Lumi Labs and iSpotify announcements.",
    "💬・general": "Community discussion and music chat.",
    "🛠️・support": "Help with iSpotify, downloads, and Discord activity.",
    "▶️・youtube": "YouTube releases, playlists, and listening links.",
    "⌘・github": "Issues, pull requests, and contribution updates.",
}
LEGACY_CHANNELS = {
    "welcome": "👋・welcome", "announcements": "📢・announcements",
    "general": "💬・general", "support": "🛠️・support",
    "youtube": "▶️・youtube", "github": "⌘・github",
}
ROLES = {
    "✦ Lumi Labs": 0x8B5CF6,
    "♫ iSpotify": 0x22C55E,
    "✧ Contributor": 0x38BDF8,
}
LEGACY_ROLES = {"Lumi Labs": "✦ Lumi Labs", "iSpotify": "♫ iSpotify", "Contributor": "✧ Contributor"}
EMOJIS = {
    "lumi": Path(__file__).resolve().parents[1] / "assets" / "discord" / "lumi.png",
    "music": Path(__file__).resolve().parents[1] / "assets" / "discord" / "music.png",
    "youtube": Path(__file__).resolve().parents[1] / "assets" / "discord" / "youtube.png",
    "github": Path(__file__).resolve().parents[1] / "assets" / "discord" / "github.png",
}


def request(method: str, path: str, token: str, payload: dict | None = None):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "LumiLabsServerSetup/1.0"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(API + path, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Discord API {exc.code}: {detail[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Discord API connection failed: {exc.reason}") from exc


def upload_emoji(guild_id: str, token: str, name: str, image_path: Path):
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {"name": name, "image": f"data:image/png;base64,{encoded}"}
    return request("POST", f"/guilds/{guild_id}/emojis", token, payload)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Set up the Lumi Labs Discord server layout")
    parser.add_argument("--dry-run", action="store_true", help="show changes without creating anything")
    args = parser.parse_args()
    settings = config()
    token = bot_token()
    guild_id = str(settings["guild_id"])
    if not token:
        print("DISCORD_BOT_TOKEN is missing from .env", file=sys.stderr)
        return 2
    try:
        guild = request("GET", f"/guilds/{guild_id}", token)
        existing_channels = request("GET", f"/guilds/{guild_id}/channels", token)
        existing_roles = request("GET", f"/guilds/{guild_id}/roles", token)
        print(f"Server: {guild.get('name', guild_id)}")
        category = next((c for c in existing_channels if c.get("type") == 4 and c.get("name") in {CATEGORY, "Lumi Labs"}), None)
        if category is None:
            print(f"  + category: {CATEGORY}")
            if not args.dry_run:
                category = request("POST", f"/guilds/{guild_id}/channels", token, {"name": CATEGORY, "type": 4})
        else:
            print(f"  = category: {CATEGORY}")
            if category.get("name") != CATEGORY and not args.dry_run:
                category = request("PATCH", f"/channels/{category['id']}", token, {"name": CATEGORY})
        category_id = category.get("id") if category else None
        for name, topic in CHANNELS.items():
            legacy = next((old for old, new in LEGACY_CHANNELS.items() if new == name), name)
            found = next((c for c in existing_channels if c.get("type") == 0 and c.get("name") in {name, legacy} and c.get("parent_id") == category_id), None)
            if found:
                print(f"  = channel: #{name}")
                if found.get("name") != name and not args.dry_run:
                    request("PATCH", f"/channels/{found['id']}", token, {"name": name, "topic": topic})
                continue
            print(f"  + channel: #{name}")
            if not args.dry_run and category_id:
                request("POST", f"/guilds/{guild_id}/channels", token, {"name": name, "type": 0, "parent_id": category_id, "topic": topic})
        for name, color in ROLES.items():
            legacy = next((old for old, new in LEGACY_ROLES.items() if new == name), name)
            existing = next((role for role in existing_roles if role.get("name") in {name, legacy}), None)
            if existing:
                print(f"  = role: {name}")
                if existing.get("name") != name and not args.dry_run:
                    request("PATCH", f"/guilds/{guild_id}/roles/{existing['id']}", token, {"name": name, "color": color})
                continue
            print(f"  + role: {name}")
            if not args.dry_run:
                request("POST", f"/guilds/{guild_id}/roles", token, {"name": name, "color": color, "hoist": False, "mentionable": False})
        existing_emojis = request("GET", f"/guilds/{guild_id}/emojis", token)
        for name, path in EMOJIS.items():
            if any(emoji.get("name") == name for emoji in existing_emojis):
                print(f"  = emoji: :{name}:")
                continue
            print(f"  + emoji: :{name}:")
            if not args.dry_run:
                upload_emoji(guild_id, token, name, path)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Dry run complete." if args.dry_run else "Lumi Labs server layout is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
