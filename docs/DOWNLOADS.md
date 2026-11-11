# Downloads and Rubika delivery

HackFire Gateway downloads files only from URLs returned by supported provider APIs and only over HTTPS from an explicit host allowlist. The downloader streams to a unique per-job directory, enforces `MAX_DOWNLOAD_SIZE_MB`, verifies Modrinth SHA-512 values when provided, and deletes the original file plus all split parts immediately after the delivery attempt finishes (success or failure). There is no persistent file cache. Download requests are limited per chat and globally bounded. On bot startup, a safety sweep removes abandoned UUID job folders older than `DOWNLOAD_ORPHAN_MAX_AGE_SECONDS` (default: one hour), covering forced restarts or power loss.

## Rubika file delivery

The official Rubika Bot API documents a two-step upload: call `requestSendFile` with type `File`, POST the file as multipart form data to the returned `upload_url`, then call `sendFile` with the returned `file_id`. The official enum documents a 50 MB maximum for general files and MP4 videos. HackFire Gateway uses a conservative 45 MiB part size so multipart overhead stays below that limit.

Files larger than the Rubika cap are split into numbered `.partNNN` attachments. Each chat has a short download cooldown and a global semaphore limits simultaneous downloads. The bot sends a manifest with the original filename, part count, and SHA-256. The receiver can join the parts in order with a binary concatenation utility; the gateway does not silently truncate oversized files.

## Commands

- `/download github owner/repository [asset-number]` — downloads a numbered asset from the latest published release. `/release owner/repository` lists the available assets.
- `/download modrinth project-slug` — downloads the primary file of the latest published version.
- `/files project-id [minecraft-version]` — lists recent CurseForge file IDs (requires an approved API key).
- `/download curseforge project-id file-id` — downloads one exact CurseForge file using official API metadata (requires an approved API key).

YouTube search returns metadata and the official watch link only. This project does not bypass DRM, subscriptions, access controls, or platform restrictions. Only download content you own or are authorized to retrieve.

Official API references: [Rubika Bot API methods](https://rubika.ir/botapi/methods) and [Rubika Bot API models](https://rubika.ir/botapi/models).
