"""Rubika menu, inline-button callbacks, and text-command handlers."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time

from app.downloads import cleanup_job_directory, download_asset, split_for_rubika
from app.providers import curseforge, github, modrinth, youtube
from app.rubika.client import RubikaClient

logger = logging.getLogger("hackfire.handlers")

WELCOME = (
    "🔥 HackFire Gateway\n\n"
    "Choose a service below. You can also type /help for command examples."
)

# Pending text searches are intentionally in-memory; they are cleared on restart.
_PENDING_SEARCH: dict[str, str] = {}
_DOWNLOAD_SEMAPHORE = asyncio.Semaphore(max(1, int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2"))))
_DOWNLOAD_LAST_USED: dict[str, float] = {}
DOWNLOAD_COOLDOWN_SECONDS = max(0, int(os.getenv("DOWNLOAD_COOLDOWN_SECONDS", "15")))


def _button(text: str, button_id: str) -> dict:
    return {"id": button_id, "type": "Simple", "button_text": text}


def _keypad(rows: list[list[tuple[str, str]]]) -> dict:
    return {"rows": [{"buttons": [_button(label, button_id) for label, button_id in row]} for row in rows if row]}


def main_keypad() -> dict:
    return _keypad([
        [("🐙 GitHub", "menu:github"), ("🟢 Modrinth", "menu:modrinth")],
        [("🟠 CurseForge", "menu:curseforge"), ("▶️ YouTube", "menu:youtube")],
        [("⬇️ Downloads", "menu:downloads"), ("ℹ️ Help", "menu:help")],
    ])


def back_keypad() -> dict:
    return _keypad([[("🏠 Main menu", "menu:home")]])


def _extract_message(update: dict):
    if update.get("type") != "NewMessage":
        return None
    message = update.get("new_message") or {}
    text = (message.get("text") or "").strip()
    chat_id = update.get("chat_id")
    if not text or not chat_id:
        return None
    return chat_id, text


def _button_id(update: dict) -> str | None:
    return ((update.get("new_message") or {}).get("aux_data") or {}).get("button_id")


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
            "Choose a download from a search result, or use one of these formats:\n"
            "/download github owner/repo [asset-number]\n"
            "/download modrinth project-slug\n"
            "/download curseforge project-id file-id",
            inline_keypad=back_keypad(),
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
            chosen = await curseforge.get_file(int(parts[2]), int(parts[3]))
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
                f"📦 {path.name} exceeds Rubika's 50 MB limit. Sending {len(parts_to_send)} numbered parts.\n"
                f"Join the parts in order to restore the original file.\nSHA-256: {digest}",
            )
        for index, part in enumerate(parts_to_send, 1):
            caption = f"{path.name} · part {index}/{len(parts_to_send)}" if len(parts_to_send) > 1 else path.name
            await client.send_file(chat_id, part, caption)
        await client.send_message(
            chat_id,
            f"✅ Delivery complete: {path.name} ({path.stat().st_size / 1048576:.1f} MB).",
            inline_keypad=main_keypad(),
        )
    except Exception as exc:
        logger.exception("Download failed for provider %s", source)
        await client.send_message(chat_id, f"⚠️ Download failed: {type(exc).__name__}. Check that provider's availability and settings.")
    finally:
        for part in parts_to_send:
            if path is not None and part != path:
                part.unlink(missing_ok=True)
        cleanup_job_directory(path)


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


async def _search(client: RubikaClient, chat_id: str, provider: str, query: str) -> None:
    await client.send_message(chat_id, f"🔎 Searching {provider.title()} for: {query}…")
    try:
        rows: list[list[tuple[str, str]]] = []
        if provider == "github":
            results = await github.search_repositories(query, 5)
            lines = []
            for item in results:
                lines.append(f"🐙 {item['full_name']}\n⭐ {item['stars']} · {item.get('language') or 'Unknown'}\n{item['url']}")
                rows.append([(f"Release: {item['full_name']}"[:40], f"release:{item['full_name']}")])
        elif provider == "modrinth":
            results = await modrinth.search_projects(query, limit=5)
            lines = []
            for item in results:
                lines.append(f"🟢 {item['title']} ({item['project_type']})\n⬇️ {item['downloads']:,} downloads\n{item['url']}")
                rows.append([(f"Versions: {item['title']}"[:40], f"versions:{item['slug']}"),
                             (f"Download: {item['title']}"[:40], f"dlmod:{item['slug']}")])
        elif provider == "curseforge":
            if not os.getenv("CURSEFORGE_API_KEY", "").strip():
                await client.send_message(
                    chat_id,
                    "🔑 CurseForge needs an approved API key. Add CURSEFORGE_API_KEY to your VPS .env file, then restart the bot.",
                    inline_keypad=back_keypad(),
                )
                return
            results = await curseforge.search_projects(query, limit=5)
            lines = []
            for item in results:
                lines.append(f"🟠 {item['name']}\nID: {item['id']} · ⬇️ {item['downloads']:,} downloads\n{item.get('website_url') or item['slug']}")
                rows.append([(f"Files: {item['name']}"[:40], f"cfiles:{item['id']}")])
        elif provider == "youtube":
            payload = await youtube.search_videos(query, 5)
            results = payload["results"]
            lines = [
                f"▶️ {item.get('title') or 'Untitled'}\n{item.get('channel') or 'Unknown channel'}\n{item.get('url') or ''}"
                for item in results
            ]
        else:
            await client.send_message(chat_id, "Unknown search provider.", inline_keypad=main_keypad())
            return
        if not results:
            await client.send_message(chat_id, "No results found. Try another search.", inline_keypad=main_keypad())
            return
        keypad_rows = rows[:8]
        keypad_rows.append([("🏠 Main menu", "menu:home")])
        await client.send_message(chat_id, ("\n\n".join(lines))[:3900], inline_keypad=_keypad(keypad_rows))
    except Exception as exc:
        logger.exception("%s search failed", provider)
        if provider == "youtube" and isinstance(exc, RuntimeError):
            message = "📡 YouTube search services are temporarily unavailable. The bot tried its configured fallbacks; please try again later."
        elif provider == "curseforge" and isinstance(exc, RuntimeError):
            message = "🔑 CurseForge is not configured. Add an approved CURSEFORGE_API_KEY to the VPS .env file."
        else:
            message = f"⚠️ {provider.title()} search failed ({type(exc).__name__}). This may be a connection issue or rate limit; try again shortly."
        await client.send_message(chat_id, message, inline_keypad=back_keypad())


async def _show_release(client: RubikaClient, chat_id: str, repository: str) -> None:
    try:
        owner, repo = repository.split("/", 1)
        release = await github.latest_release(owner, repo)
        if not release:
            await client.send_message(chat_id, "No published release found.", inline_keypad=back_keypad())
            return
        lines = [f"🐙 {repository} — {release.get('name') or release.get('tag')}"]
        rows = []
        for index, asset in enumerate(release.get("assets", [])[:8], 1):
            size_mb = (asset.get("size") or 0) / (1024 * 1024)
            lines.append(f"📦 {index}. {asset['name']} · {size_mb:.1f} MB")
            rows.append([(f"⬇️ Download #{index}", f"dlgh:{repository}:{index}")])
        rows.append([("🏠 Main menu", "menu:home")])
        await client.send_message(chat_id, "\n".join(lines)[:3900], inline_keypad=_keypad(rows))
    except Exception as exc:
        logger.exception("Release lookup failed")
        await client.send_message(chat_id, f"⚠️ Release lookup failed ({type(exc).__name__}).", inline_keypad=back_keypad())


async def _show_versions(client: RubikaClient, chat_id: str, slug: str) -> None:
    try:
        versions = await modrinth.project_versions(slug, limit=8)
        if not versions:
            await client.send_message(chat_id, "No versions found.", inline_keypad=back_keypad())
            return
        lines = [
            f"🟢 {item['version_number']} — {', '.join(item['loaders']) or 'Any loader'}\nMC: {', '.join(item['game_versions'][:5])}"
            for item in versions
        ]
        await client.send_message(chat_id, "\n\n".join(lines)[:3900], inline_keypad=_keypad([
            [("⬇️ Download latest", f"dlmod:{slug}")],
            [("🏠 Main menu", "menu:home")],
        ]))
    except Exception as exc:
        logger.exception("Modrinth versions lookup failed")
        await client.send_message(chat_id, f"⚠️ Version lookup failed ({type(exc).__name__}).", inline_keypad=back_keypad())


async def _show_curseforge_files(client: RubikaClient, chat_id: str, project_id: str) -> None:
    try:
        found = await curseforge.list_files(int(project_id), limit=8)
        if not found:
            await client.send_message(chat_id, "No files found for this project.", inline_keypad=back_keypad())
            return
        lines, rows = [], []
        for item in found:
            name = item.get("display_name") or item.get("file_name")
            size = (item.get("file_length") or 0) / 1048576
            lines.append(f"🟠 {name}\nID: {item['id']} · {size:.1f} MB")
            if item.get("download_url"):
                rows.append([(f"⬇️ {name}"[:40], f"dlcf:{project_id}:{item['id']}")])
        rows.append([("🏠 Main menu", "menu:home")])
        await client.send_message(chat_id, "\n\n".join(lines)[:3900], inline_keypad=_keypad(rows[:9]))
    except Exception as exc:
        logger.exception("CurseForge file lookup failed")
        await client.send_message(chat_id, f"⚠️ File lookup failed ({type(exc).__name__}). Check API configuration.", inline_keypad=back_keypad())


async def handle_update(client: RubikaClient, update: dict) -> None:
    extracted = _extract_message(update)
    if not extracted:
        return
    chat_id, text = extracted
    lowered = text.lower()
    button_id = _button_id(update)

    if button_id:
        if button_id == "menu:home":
            _PENDING_SEARCH.pop(chat_id, None)
            await client.send_message(chat_id, WELCOME, inline_keypad=main_keypad())
            return
        if button_id == "menu:help":
            await client.send_message(chat_id, WELCOME + "\n\nYou can still use /github, /modrinth, /curseforge, /youtube and /download.", inline_keypad=main_keypad())
            return
        if button_id == "menu:downloads":
            await client.send_message(
                chat_id,
                "⬇️ Downloads\nChoose an item from a GitHub, Modrinth, or CurseForge search result to get a download button. You can also use /download with a provider and project identifier.",
                inline_keypad=main_keypad(),
            )
            return
        if button_id.startswith("menu:"):
            provider = button_id.split(":", 1)[1]
            if provider in {"github", "modrinth", "curseforge", "youtube"}:
                _PENDING_SEARCH[chat_id] = provider
                await client.send_message(chat_id, f"🔎 {provider.title()} search\nNow send the words you want to search for.", inline_keypad=back_keypad())
                return
        if button_id.startswith("release:"):
            await _show_release(client, chat_id, button_id.split(":", 1)[1])
            return
        if button_id.startswith("versions:"):
            await _show_versions(client, chat_id, button_id.split(":", 1)[1])
            return
        if button_id.startswith("cfiles:"):
            await _show_curseforge_files(client, chat_id, button_id.split(":", 1)[1])
            return
        if button_id.startswith("dlgh:"):
            _, repository, index = button_id.split(":", 2)
            await _download_command(client, chat_id, ["/download", "github", repository, index])
            return
        if button_id.startswith("dlmod:"):
            await _download_command(client, chat_id, ["/download", "modrinth", button_id.split(":", 1)[1]])
            return
        if button_id.startswith("dlcf:"):
            _, project_id, file_id = button_id.split(":", 2)
            await _download_command(client, chat_id, ["/download", "curseforge", project_id, file_id])
            return

    if lowered in {"/start", "start", "/help", "help"}:
        _PENDING_SEARCH.pop(chat_id, None)
        await client.send_message(chat_id, WELCOME, inline_keypad=main_keypad())
        return

    if lowered.startswith("/download"):
        _PENDING_SEARCH.pop(chat_id, None)
        await _download_command(client, chat_id, text.split())
        return

    if lowered.startswith("/release"):
        parts = text.split(maxsplit=1)
        if len(parts) != 2 or "/" not in parts[1]:
            await client.send_message(chat_id, "Usage: /release owner/repository", inline_keypad=back_keypad())
        else:
            await _show_release(client, chat_id, parts[1])
        return

    if lowered.startswith("/files"):
        parts = text.split()
        if len(parts) not in (2, 3):
            await client.send_message(chat_id, "Usage: /files <CurseForge-project-id> [Minecraft-version]")
            return
        try:
            found = await curseforge.list_files(int(parts[1]), game_version=parts[2] if len(parts) == 3 else None, limit=8)
            lines = [f"🟠 {item['display_name'] or item['file_name']}\nID: {item['id']} · {((item.get('file_length') or 0) / 1048576):.1f} MB" for item in found]
            await client.send_message(chat_id, ("\n\n".join(lines) if lines else "No CurseForge files found.")[:3900], inline_keypad=back_keypad())
        except Exception as exc:
            logger.exception("CurseForge file lookup failed")
            await client.send_message(chat_id, f"⚠️ File lookup failed ({type(exc).__name__}). Check the CurseForge API key.")
        return

    if lowered.startswith("/versions"):
        parts = text.split(maxsplit=1)
        if len(parts) != 2:
            await client.send_message(chat_id, "Usage: /versions <Modrinth-project-slug>")
        else:
            await _show_versions(client, chat_id, parts[1])
        return

    for command, provider in (("/github", "github"), ("/modrinth", "modrinth"), ("/curseforge", "curseforge"), ("/youtube", "youtube")):
        if lowered == command or lowered.startswith(command + " "):
            query = text[len(command):].strip()
            if not query:
                _PENDING_SEARCH[chat_id] = provider
                await client.send_message(chat_id, f"Send the search terms for {provider.title()}.", inline_keypad=back_keypad())
            else:
                _PENDING_SEARCH.pop(chat_id, None)
                await _search(client, chat_id, provider, query)
            return

    pending_provider = _PENDING_SEARCH.pop(chat_id, None)
    if pending_provider:
        await _search(client, chat_id, pending_provider, text)
        return

    await client.send_message(chat_id, "Choose a service from the menu below, or send /help.", inline_keypad=main_keypad())
