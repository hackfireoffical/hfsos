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
- Rubika commands: `/github`, `/release`, `/modrinth`, `/versions`, `/curseforge`, `/youtube`, `/help`.
- YouTube provider fallback order: YouTube Data API (if configured), healthy Invidious instances, then Piped instances.
- Secrets are read from environment variables; real credentials must never be committed.

## Run locally or on the VPS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env locally and set RUBIKA_BOT_TOKEN.
python -m app.bot
```

Start the HTTP API separately:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

OpenAPI docs are available at `/docs` while the API is running.

## Environment variables

- `RUBIKA_BOT_TOKEN` — required to run the Rubika bot.
- `GITHUB_TOKEN` — optional; improves GitHub API rate limits.
- `YOUTUBE_API_KEY` — optional; primary YouTube search provider.
- `CURSEFORGE_API_KEY` — optional; required for CurseForge integration.
- `MAX_CONCURRENT_DOWNLOADS` — reserved for the download worker milestone.

## Planned next

- Search result pagination and richer Rubika keyboards.
- Download queue with host allowlists, bounded concurrency, cancellation, and cleanup.
- Authorized GitHub/Modrinth/CurseForge file retrieval.
- Rubika file upload, verified split delivery for files beyond confirmed platform limits.
- SQLite job history, user permissions, and admin controls.

## Safety and reliability

Public Invidious and Piped instances are third-party services and can disappear or rate-limit requests. The bot rotates through discovered instances but cannot guarantee availability. Media retrieval will be limited to content the user owns or is authorized to download. Large-file splitting and upload behavior will be implemented only after Rubika's current API limits and terms are verified.

## Security

- Keep the real `.env` file out of Git.
- Never paste bot tokens or API keys into issues, commits, screenshots, or chat.
- Do not expose the API publicly without authentication and rate limiting.
