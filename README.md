# HackFire Gateway

A Rubika-based search and delivery bot for selected content platforms.

## Supported integrations

- **YouTube** — search metadata using the official Data API when configured, then public Invidious instances, then Piped instances.
- **GitHub** — repository search and latest release/asset metadata.
- **Modrinth** — project search and version/file metadata.
- **CurseForge** — Minecraft project search and file metadata; requires an approved API key.

## Current functionality

- FastAPI service with health endpoint and interactive API docs.
- Rubika Bot API v3 client using long polling.
- Rubika commands: `/github`, `/release`, `/modrinth`, `/versions`, `/curseforge`, `/files`, `/youtube`, `/download`, `/help`.
- Authorized GitHub release, Modrinth version, and CurseForge file downloads with bounded streaming and provider hash verification where available.
- Rubika file upload using the official two-step `requestSendFile` → multipart upload → `sendFile` flow; files over the documented 50 MB limit are split into 45 MiB parts.
- YouTube provider fallback order: YouTube Data API (if configured), healthy Invidious instances, then Piped instances.
- Secrets are read from environment variables; real credentials must never be committed.

## Install on Ubuntu VPS

Recommended: Ubuntu 24.04 LTS with root/sudo access. systemd is preferred; restricted VPS containers without systemd are supported through Supervisor.

```bash
curl -fsSL https://raw.githubusercontent.com/hackfireoffical/hfsos/main/install.sh -o install.sh
sudo bash install.sh
rm -f install.sh
```

The installer clones the project to `/opt/hackfire-gateway`, creates a restricted system user and Python virtual environment, prompts privately for your Rubika token, and starts the bot and localhost-only API using systemd or Supervisor, depending on the VPS environment.

Full instructions: [docs/VPS_INSTALL.md](docs/VPS_INSTALL.md).

## Service management

```bash
sudo bash /opt/hackfire-gateway/scripts/status.sh
# On systemd: sudo journalctl -u hackfire-gateway-bot -f
# Without systemd: sudo tail -f /var/log/hackfire-gateway-bot.log
curl http://127.0.0.1:8000/health
sudo bash /opt/hackfire-gateway/scripts/update.sh
```

The API listens only on `127.0.0.1:8000`; do not expose it publicly until authentication and rate limiting are implemented.

## Environment variables

- `RUBIKA_BOT_TOKEN` — required to run the Rubika bot.
- `GITHUB_TOKEN` — optional; improves GitHub API rate limits.
- `YOUTUBE_API_KEY` — optional; primary YouTube search provider.
- `CURSEFORGE_API_KEY` — optional; required for CurseForge integration.

## Planned next

- Search result pagination and richer Rubika keyboards.
- Persistent SQLite job history and admin controls.

## Safety and reliability

Public Invidious and Piped instances are third-party services and can disappear or rate-limit requests. The bot discovers the complete HTTPS instance lists, probes them with bounded concurrency, and falls back to Piped if Invidious is unavailable. Third-party instances can still disappear or rate-limit requests. Media retrieval will be limited to content the user owns or is authorized to download. Large files are split conservatively because the official Rubika API documents a 50 MB general-file cap. The gateway downloads only from provider API asset URLs on an explicit HTTPS host allowlist.

## Security

- Keep the real `.env` file out of Git.
- Never paste bot tokens or API keys into issues, commits, screenshots, or chat.
- Do not expose the API publicly without authentication and rate limiting.


Download behavior and Rubika file-delivery details: [docs/DOWNLOADS.md](docs/DOWNLOADS.md).
