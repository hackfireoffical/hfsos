# HackFire Gateway

A Rubika-based search and delivery bot for selected content platforms.

## Supported integrations

- GitHub: repository search and release/asset metadata.
- Modrinth: project search, version lookup, and permitted project-file downloads.
- CurseForge: planned; requires compliant API access and credentials.
- YouTube: search and metadata through a primary provider with Invidious and Piped fallbacks. Media delivery is limited to content the user owns or is authorized to download.

## Planned capabilities

- Persian and English Rubika interface.
- Search menus and paginated results.
- Asynchronous download queue with bounded concurrency.
- Retry and provider health tracking.
- Temporary file storage and automatic cleanup.
- Rubika delivery where supported by the platform's upload limits.
- Large-file splitting only if Rubika's terms and upload behavior permit it.
- SHA-256 integrity checks.
- SQLite persistence for users, jobs, and history.
- Environment-based secrets; never commit bot tokens.

## Architecture

Rubika Bot -> Application / Handlers -> Platform providers -> Job queue -> Temporary storage -> Rubika delivery.

The YouTube provider manager will try the configured primary provider, then healthy Invidious instances, then Piped instances.

## Development status

This repository is the project source of truth. Integrations and delivery behavior will be implemented and tested incrementally. Public third-party instances are best-effort and are not guaranteed to be online.

## Security

- Put credentials in environment variables or a local .env file.
- .env is ignored by Git.
- Never commit bot tokens, API keys, or private credentials.
- Restrict bot access and download concurrency before public deployment.

## License

To be selected by the repository owner.
