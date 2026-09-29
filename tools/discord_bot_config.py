"""Load and validate the local Discord bot configuration without exposing secrets."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.lstrip("\ufeff").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        os.environ.setdefault(key, value)


def config() -> dict[str, str | bool]:
    load_dotenv()
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    client_id = os.getenv("DISCORD_CLIENT_ID", "1554388523442901005").strip()
    guild_id = os.getenv("DISCORD_GUILD_ID", "1554149647621029979").strip()
    return {
        "token_configured": bool(token),
        "client_id": client_id,
        "guild_id": guild_id,
        "name": os.getenv("DISCORD_BOT_NAME", "Lumi Labs"),
        "description": os.getenv("DISCORD_BOT_DESCRIPTION", "Clean YouTube music tools for the Lumi Labs community"),
        "style": os.getenv("DISCORD_BOT_STYLE", "minimal"),
        "font": os.getenv("DISCORD_BOT_FONT", "Inter"),
        "youtube_url": os.getenv("DISCORD_YOUTUBE_URL", "https://www.youtube.com"),
        "github_url": os.getenv("DISCORD_GITHUB_URL", "https://github.com/RubinLabs26/ISpotify"),
    }


def bot_token() -> str:
    load_dotenv()
    return os.getenv("DISCORD_BOT_TOKEN", "").strip()


if __name__ == "__main__":
    print(json.dumps(config(), indent=2))
