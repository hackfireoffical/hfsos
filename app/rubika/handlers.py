"""Message routing for the first HackFire Gateway Rubika bot milestone."""
from __future__ import annotations

from app.providers import curseforge, github, modrinth, youtube
from app.rubika.client import RubikaClient


WELCOME = (
    "🔥 HackFire Gateway\n\n"
    "Search supported platforms through Rubika.\n\n"
    "Commands:\n"
    "/github <query> — search repositories\n"
    "/release <owner/repo> — latest GitHub release\n"
    "/modrinth <query> — search mods and modpacks\n"
    "/versions <project-slug> — list Modrinth versions\n"
    "/curseforge <query> — search CurseForge (API key required)\n"
    "/youtube <query> — search YouTube metadata\n"
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


async def handle_update(client: RubikaClient, update: dict) -> None:
    extracted = _extract_message(update)
    if not extracted:
        return
    chat_id, text = extracted
    lowered = text.lower()

    if lowered in {"/start", "start", "/help", "help"}:
        await client.send_message(chat_id, WELCOME)
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
                lines.append(f"📦 {asset['name']} · {size_mb:.1f} MB\n{asset['download_url']}")
            lines.append(release.get("url") or "")
            await client.send_message(chat_id, "\n\n".join(lines)[:3900])
        except Exception as exc:
            await client.send_message(chat_id, f"⚠️ Release lookup failed ({type(exc).__name__}).")
        return

    if lowered.startswith("/versions"):
        parts = text.split(maxsplit=1)
        if len(parts) != 2:
            await client.send_message(chat_id, "Usage: /versions <Modrinth-project-slug>")
            return
        try:
            versions = await modrinth.project_versions(parts[1], limit=8)
            lines = [
                f"🟢 {item['version_number']} — {', '.join(item['loaders']) or 'Any loader'}\n"
                f"MC: {', '.join(item['game_versions'][:5])}\n"
                f"{next((file['url'] for file in item['files'] if file['primary']), item['files'][0]['url'] if item['files'] else '')}"
                for item in versions
            ]
            await client.send_message(chat_id, ("\n\n".join(lines) if lines else "No versions found.")[:3900])
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
                        f"🐙 {item['full_name']}\n⭐ {item['stars']} · {item.get('language') or 'Unknown'}\n{item['url']}"
                        for item in results
                    ]
                elif provider_name == "modrinth":
                    results = await modrinth.search_projects(query, limit=5)
                    lines = [
                        f"🟢 {item['title']} ({item['project_type']})\n⬇️ {item['downloads']:,}\n{item['url']}"
                        for item in results
                    ]
                elif provider_name == "curseforge":
                    results = await curseforge.search_projects(query, limit=5)
                    lines = [
                        f"🟠 {item['name']}\n⬇️ {item['downloads']:,}\n{item.get('website_url') or item['slug']}"
                        for item in results
                    ]
                else:
                    payload = await youtube.search_videos(query, 5)
                    results = payload["results"]
                    lines = [
                        f"▶️ {item.get('title') or 'Untitled'}\n{item.get('channel') or 'Unknown channel'}\n{item.get('url') or ''}"
                        for item in results
                    ]
                await client.send_message(chat_id, ("\n\n".join(lines) if lines else "No results found.")[:3900])
            except Exception as exc:
                await client.send_message(chat_id, f"⚠️ Search failed ({type(exc).__name__}). Check provider configuration and try again.")
            return

    await client.send_message(chat_id, "I didn't recognize that command. Send /help to see available commands.")
