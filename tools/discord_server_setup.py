"""Idempotently create the minimal Lumi Labs Discord server layout."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from discord_bot_config import bot_token, config

API = "https://discord.com/api/v10"

CATEGORY = "Lumi Labs"
CHANNELS = {
    "welcome": "Start here for Lumi Labs and iSpotify updates.",
    "announcements": "Official Lumi Labs and iSpotify announcements.",
    "general": "Community discussion and music chat.",
    "support": "Help with iSpotify, downloads, and Discord activity.",
    "youtube": "YouTube releases, playlists, and listening links.",
    "github": "Issues, pull requests, and contribution updates.",
}
ROLES = {
    "Lumi Labs": 0x8B5CF6,
    "iSpotify": 0x22C55E,
    "Contributor": 0x38BDF8,
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


def main() -> int:
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
        category = next((c for c in existing_channels if c.get("type") == 4 and c.get("name") == CATEGORY), None)
        if category is None:
            print(f"  + category: {CATEGORY}")
            if not args.dry_run:
                category = request("POST", f"/guilds/{guild_id}/channels", token, {"name": CATEGORY, "type": 4})
        else:
            print(f"  = category: {CATEGORY}")
        category_id = category.get("id") if category else None
        for name, topic in CHANNELS.items():
            found = next((c for c in existing_channels if c.get("type") == 0 and c.get("name") == name and c.get("parent_id") == category_id), None)
            if found:
                print(f"  = channel: #{name}")
                continue
            print(f"  + channel: #{name}")
            if not args.dry_run and category_id:
                request("POST", f"/guilds/{guild_id}/channels", token, {"name": name, "type": 0, "parent_id": category_id, "topic": topic})
        for name, color in ROLES.items():
            if any(role.get("name") == name for role in existing_roles):
                print(f"  = role: {name}")
                continue
            print(f"  + role: {name}")
            if not args.dry_run:
                request("POST", f"/guilds/{guild_id}/roles", token, {"name": name, "color": color, "hoist": False, "mentionable": False})
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Dry run complete." if args.dry_run else "Lumi Labs server layout is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
