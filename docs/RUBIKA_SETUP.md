# Rubika bot setup

The bot uses the official Rubika Bot API v3 over HTTPS and starts with long polling. The official documentation describes `getUpdates` polling with `offset_id` / `next_offset_id`, and `sendMessage` for replies.

## Configure

1. Copy `.env.example` to `.env`.
2. Set `RUBIKA_BOT_TOKEN` in the local `.env` file.
3. Install dependencies in a virtual environment.
4. Start the bot with `python -m app.bot`.

Never commit the real `.env` file or share the token in chat, screenshots, logs, or issue reports.

## Current commands

- `/start` and `/help`
- `/github <query>`
- `/modrinth <query>`
- `/youtube <query>`

This first bot milestone returns search metadata and links. File delivery, queue management, user permissions, and download workflows are not implemented yet.

## Notes

- Long polling is selected because it does not require a public HTTPS webhook endpoint.
- The bot token is embedded in the API request path by Rubika's documented API format. The client avoids logging request URLs.
- Search providers need outbound internet access from the VPS.
- YouTube search tries the configured YouTube Data API key first, then public Invidious instances, then Piped instances.
