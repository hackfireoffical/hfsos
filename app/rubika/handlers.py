"""Message routing for HackFire Gateway."""
from __future__ import annotations

import asyncio
import hashlib
import os
import time

from app.downloads import download_asset, split_for_rubika
from app.providers import curseforge, github, modrinth, youtube
from app.rubika.client import RubikaClient


WELCOME = (
    "🔥 HackFire Gateway\\n\\n"
    "Search and retrieve supported files through Rubika.\\n\\n"
    "Commands:\\n"
    "/github <query> — search repositories\\n"
    "/release <owner/repo> — latest GitHub release\\n"
    "/modrinth <query> — search mods and modpacks\\n"
    "/versions <project-slug> — list Modrinth versions\\n"
    "/curseforge <query> — search CurseForge (API key required)\\n"
    "/youtube <query> — search YouTube metadata\\n"
    "/download github owner/repo — download first latest-release asset\\n"
    "/download modrinth project-slug — download latest primary file\\n"
    "/download curseforge project-id file-id — download a CurseForge file\\n"
    "/help — show this message"
)


def _extract_message(update: dict):
    if update.get("type") != "NewMessage":
        return None
    message = update.get("new_message") or {}
    text = (message.get("text") or "").strip()
    chat_id = update.get("chat_id")
    if not text or not chat_id:
        return None
    return chat_id, text


_DOWNLOAD_SEMAPHORE = asyncio.Semaphore(max(1, int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2"))))
_DOWNLOAD_LAST_USED: dict[str, float] = {}
DOWNLOAD_COOLDOWN_SECONDS = max(0, int(os.getenv("DOWNLOAD_COOLDOWN_SECONDS", "15")))


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _download_command_inner(client: RubikaClient, chat_id: str, parts: list[str]) -> None:
    if len(parts) < 3:
        await client.send_message(
            chat_id,
            "Usage:\\n/download github owner/repo\\n/download modrinth project-slug\\n/download curseforge project-id file-id",
        )
        return

    source = parts[1].lower()
    path = None
    parts_to_send = []
    try:
        url = filename = expected_sha512 = None
        if source == "github" and len(parts) in (3, 4) and "/" in parts[2]:
            owner, repository = parts[2].split("/", 1)
            release = await github.latest_release(owner, repository)
            assets = (release or {}).get("assets") or []
            if not assets:
                await client.send_message(chat_id, "No downloadable asset exists in the latest release.")
                return
            asset_number = int(parts[3]) if len(parts) == 4 else 1
            if asset_number < 1 or asset_number > len(assets):
                await client.send_message(chat_id, f"Choose an asset number from 1 to {len(assets)}.")
                return
            asset = assets[asset_number - 1]
            url, filename = asset.get("download_url"), asset.get("name")
        elif source == "modrinth" and len(parts) == 3:
            versions = await modrinth.project_versions(parts[2], limit=1)
            files = (versions[0].get("files") or []) if versions else []
            chosen = next((item for item in files if item.get("primary")), files[0] if files else None)
            if not chosen:
                await client.send_message(chat_id, "No downloadable file found for that Modrinth project.")
                return
            url, filename, expected_sha512 = chosen.get("url"), chosen.get("filename"), chosen.get("sha512")
        elif source == "curseforge" and len(parts) == 4:
            files = await curseforge.list_files(int(parts[2]), limit=50)
            chosen = next((item for item in files if str(item.get("id")) == parts[3]), None)
            if not chosen or not chosen.get("download_url"):
                await client.send_message(chat_id, "That CurseForge file is unavailable for direct download.")
                return
            url, filename = chosen.get("download_url"), chosen.get("file_name")
        else:
            await client.send_message(chat_id, "Invalid download command. Send /help for examples.")
            return

        if not url or not filename:
            await client.send_message(chat_id, "The provider did not return a downloadable file.")
            return

        await client.send_message(chat_id, f"⬇️ Downloading {filename}…")
        path = await download_asset(url, filename, expected_sha512)
        parts_to_send = split_for_rubika(path)
        digest = _sha256(path)
        if len(parts_to_send) > 1:
            await client.send_message(
                chat_id,
                f"📦 {path.name} exceeds Rubika's 50 MB limit. Sending {len(parts_to_send)} numbered parts.\\n"
                f"Join the parts in order to restore the original file.\\nSHA-256: {digest}",
            )

        for index, part in enumerate(parts_to_send, 1):
            caption = f"{path.name} · part {index}/{len(parts_to_send)}" if len(parts_to_send) > 1 else path.name
            await client.send_file(chat_id, part, caption)

        await client.send_message(
            chat_id,
            f"✅ Delivery complete: {path.name} ({path.stat().st_size / 1048576:.1f} MB).",
        )
    except Exception as exc:
        await client.send_message(
            chat_id,
            f"⚠️ Download failed ({type(exc).__name__}). Check provider availability/API key and try again.",
        )
    finally:
        for part in parts_to_send:
            if path is not None and part != path:
                part.unlink(missing_ok=True)
        if path is not None:
            path.unlink(missing_ok=True)



async def _download_command(client: RubikaClient, chat_id: str, parts: list[str]) -> None:
    now = time.monotonic()
    previous = _DOWNLOAD_LAST_USED.get(chat_id, 0.0)
    wait = DOWNLOAD_COOLDOWN_SECONDS - (now - previous)
    if wait > 0:
        await client.send_message(chat_id, f"Please wait {int(wait) + 1}s before starting another download.")
        return
    _DOWNLOAD_LAST_USED[chat_id] = now
    async with _DOWNLOAD_SEMAPHORE:
        await _download_command_inner(client, chat_id, parts)


async def handle_update(client: RubikaClient, update: dict) -> None:
    extracted = _extract_message(update)
    if not extracted:
        return
    chat_id, text = extracted
    lowered = text.lower()

    if lowered in {"/start", "start", "/help", "help"}:
        await client.send_message(chat_id, WELCOME)
        return

    if lowered.startswith("/download"):
        await _download_command(client, chat_id, text.split())
        return

    if lowered.startswith("/release"):
        parts = text.split(maxsplit=1)
        if len(parts) != 2 or "/" not in parts[1]:
            await client.send_message(chat_id, "Usage: /release owner/repository")
            return
        owner, repository = parts[1].split("/", 1)
        try:
            release = await github.latest_release(owner, repository)
            if not release:
                await client.send_message(chat_id, "No published release found.")
                return
            lines = [f"🐙 {owner}/{repository} — {release.get('name') or release.get('tag')}"]
            for asset in release.get("assets", [])[:8]:
                size_mb = (asset.get("size") or 0) / (1024 * 1024)
                lines.append(f"📦 {asset['name']} · {size_mb:.1f} MB\\n{asset['download_url']}")
            lines.append(release.get("url") or "")
            await client.send_message(chat_id, "\\n\\n".join(lines)[:3900])
        except Exception as exc:
            await client.send_message(chat_id, f"⚠️ Release lookup failed ({type(exc).__name__}).")
        return


    if lowered.startswith("/files"):
        parts = text.split()
        if len(parts) not in (2, 3):
            await client.send_message(chat_id, "Usage: /files <CurseForge-project-id> [Minecraft-version]")
            return
        try:
            found = await curseforge.list_files(int(parts[1]), game_version=parts[2] if len(parts) == 3 else None, limit=10)
            lines = [
                f"🟠 {item['display_name'] or item['file_name']}\\nID: {item['id']} · {((item.get('file_length') or 0) / 1048576):.1f} MB"
                for item in found
            ]
            await client.send_message(chat_id, ("\\n\\n".join(lines) if lines else "No CurseForge files found.")[:3900])
        except Exception as exc:
            await client.send_message(chat_id, f"⚠️ File lookup failed ({type(exc).__name__}). Check the CurseForge API key.")
        return

    if lowered.startswith("/versions"):
        parts = text.split(maxsplit=1)
        if len(parts) != 2:
            await client.send_message(chat_id, "Usage: /versions <Modrinth-project-slug>")
            return
        try:
            versions = await modrinth.project_versions(parts[1], limit=8)
            lines = [
                f"🟢 {item['version_number']} — {', '.join(item['loaders']) or 'Any loader'}\\n"
                f"MC: {', '.join(item['game_versions'][:5])}\\n"
                f"{next((file['url'] for file in item['files'] if file['primary']), item['files'][0]['url'] if item['files'] else '')}"
                for item in versions
            ]
            await client.send_message(chat_id, ("\\n\\n".join(lines) if lines else "No versions found.")[:3900])
        except Exception as exc:
            await client.send_message(chat_id, f"⚠️ Version lookup failed ({type(exc).__name__}).")
        return

    for command, provider_name in (
        ("/github", "github"),
        ("/modrinth", "modrinth"),
        ("/curseforge", "curseforge"),
        ("/youtube", "youtube"),
    ):
        if lowered.startswith(command + " ") or lowered == command:
            query = text[len(command):].strip()
            if not query:
                await client.send_message(chat_id, f"Usage: {command} <search terms>")
                return
            await client.send_message(chat_id, f"🔎 Searching {provider_name} for: {query}")
            try:
                if provider_name == "github":
                    results = await github.search_repositories(query, 5)
                    lines = [
                        f"🐙 {item['full_name']}\\n⭐ {item['stars']} · {item.get('language') or 'Unknown'}\\n{item['url']}"
                        for item in results
                    ]
                elif provider_name == "modrinth":
                    results = await modrinth.search_projects(query, limit=5)
                    lines = [
                        f"🟢 {item['title']} ({item['project_type']})\\n⬇️ {item['downloads']:,}\\n{item['url']}"
                        for item in results
                    ]
                elif provider_name == "curseforge":
                    results = await curseforge.search_projects(query, limit=5)
                    lines = [
                        f"🟠 {item['name']}\\n⬇️ {item['downloads']:,}\\n{item.get('website_url') or item['slug']}"
                        for item in results
                    ]
                else:
                    payload = await youtube.search_videos(query, 5)
                    results = payload["results"]
                    lines = [
                        f"▶️ {item.get('title') or 'Untitled'}\\n{item.get('channel') or 'Unknown channel'}\\n{item.get('url') or ''}"
                        for item in results
                    ]
                await client.send_message(chat_id, ("\\n\\n".join(lines) if lines else "No results found.")[:3900])
            except Exception as exc:
                await client.send_message(chat_id, f"⚠️ Search failed ({type(exc).__name__}). Check provider configuration and try again.")
            return

    await client.send_message(chat_id, "I didn't recognize that command. Send /help to see available commands.")
