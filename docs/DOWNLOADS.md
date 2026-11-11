# Downloads and Rubika delivery

HackFire Gateway downloads files only from URLs returned by supported provider APIs and only over HTTPS from an explicit host allowlist. The downloader streams to disk, enforces `MAX_DOWNLOAD_SIZE_MB`, and verifies Modrinth SHA-512 values when provided.

## Rubika file delivery

The official Rubika Bot API documents a two-step upload: call `requestSendFile` with type `File`, POST the file as multipart form data to the returned `upload_url`, then call `sendFile` with the returned `file_id`. The official enum documents a 50 MB maximum for general files and MP4 videos. HackFire Gateway uses a conservative 45 MiB part size so multipart overhead stays below that limit.

Files larger than the Rubika cap are split into numbered `.partNNN` attachments. The bot sends a manifest with the original filename, part count, and SHA-256. The receiver can join the parts in order with a binary concatenation utility; the gateway does not silently truncate oversized files.

## Commands

- `/download github owner/repository` — downloads the first asset of the latest published release.
- `/download modrinth project-slug` — downloads the primary file of the latest published version.
- `/download curseforge project-id file-id` — downloads a CurseForge file using its official API metadata (requires an approved API key).

YouTube search returns metadata and the official watch link only. This project does not bypass DRM, subscriptions, access controls, or platform restrictions. Only download content you own or are authorized to retrieve.

Official API references: [Rubika Bot API methods](https://rubika.ir/botapi/methods) and [Rubika Bot API models](https://rubika.ir/botapi/models).
