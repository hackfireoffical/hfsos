"""Message routing for the first HackFire Gateway Rubika bot milestone."""
from __future__ import annotations

from app.providers import github, modrinth, youtube
from app.rubika.client import RubikaClient


WELCOME = (
    "🔥 HackFire Gateway\n\n"
    "Search international project catalogs through Rubika.\n\n"
    "Commands:\n"
    "/github <query> — search GitHub repositories\n"
    "/modrinth <query> — search Modrinth projects\n"
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

    for command, provider_name in (
        ("/github", "github"),
        ("/modrinth", "modrinth"),
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
                else:
                    payload = await youtube.search_videos(query, 5)
                    results = payload["results"]
                    lines = [
                        f"▶️ {item.get('title') or 'Untitled'}\n{item.get('channel') or 'Unknown channel'}\n{item.get('url') or ''}"
                        for item in results
                    ]
                if not lines:
                    await client.send_message(chat_id, "No results found.")
                else:
                    await client.send_message(chat_id, "\n\n".join(lines)[:3900])
            except Exception as exc:
                await client.send_message(chat_id, f"⚠️ Search failed ({type(exc).__name__}). Please try again later.")
            return

    await client.send_message(chat_id, "I didn't recognize that command. Send /help to see available commands.")
