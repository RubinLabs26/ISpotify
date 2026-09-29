# Lumi Labs Discord bot configuration

The bot configuration is local-only. Copy `.env.example` to `.env`, set the
token, and keep `.env` out of Git. The repository already ignores it.

The configured bot application is `1554388523442901005` and the setup server is
`1554149647621029979`. The profile defaults to a minimal Lumi Labs style with
Inter typography and YouTube/GitHub links.

Check the setup without printing the token:

```bash
python tools/discord_bot_config.py
```

Set up the clean server layout (category, channels, and roles) idempotently:

```bash
python tools/discord_server_setup.py
```

Use `--dry-run` to preview changes. The setup creates a `Lumi Labs` category
with `welcome`, `announcements`, `general`, `support`, `youtube`, and `github`
channels, plus `Lumi Labs`, `iSpotify`, and `Contributor` roles. Existing items
with the same names are left untouched.

Bot tokens are passwords. If a token is pasted into chat, a screenshot, an
issue, or a log, regenerate it immediately in Discord Developer Portal and
replace the value in `.env`.
