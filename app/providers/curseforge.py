"""CurseForge Core API provider for Minecraft projects.

Requires an API key issued for this application by CurseForge.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

API = "https://api.curseforge.com/v1"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
MINECRAFT_GAME_ID = 432
MINECRAFT_MOD_CLASS_ID = 6


def _headers() -> dict[str, str]:
    key = os.getenv("CURSEFORGE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("CURSEFORGE_API_KEY is not configured")
    return {"Accept": "application/json", "x-api-key": key, "User-Agent": "HackFireGateway/0.1"}


async def search_projects(query: str, project_type: str = "mod", limit: int = 10) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []
    # CurseForge Minecraft class IDs: 6=mods, 4471=modpacks.
    class_id = 4471 if project_type == "modpack" else MINECRAFT_MOD_CLASS_ID
    params = {
        "gameId": MINECRAFT_GAME_ID,
        "classId": class_id,
        "searchFilter": query,
        "sortField": 2,
        "sortOrder": "desc",
        "index": 0,
        "pageSize": max(1, min(limit, 30)),
    }
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=_headers()) as client:
        response = await client.get(f"{API}/mods/search", params=params)
        response.raise_for_status()
        payload = response.json()
    return [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "slug": item.get("slug"),
            "summary": item.get("summary"),
            "downloads": item.get("downloadCount", 0),
            "website_url": (item.get("links") or {}).get("websiteUrl"),
            "logo_url": (item.get("logo") or {}).get("url"),
        }
        for item in payload.get("data", [])
    ]


async def list_files(mod_id: int, game_version: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    if mod_id <= 0:
        raise ValueError("Invalid CurseForge project ID.")
    params: dict[str, Any] = {"index": 0, "pageSize": max(1, min(limit, 50))}
    if game_version:
        params["gameVersion"] = game_version
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=_headers()) as client:
        response = await client.get(f"{API}/mods/{mod_id}/files", params=params)
        response.raise_for_status()
        payload = response.json()
    return [
        {
            "id": item.get("id"),
            "display_name": item.get("displayName"),
            "file_name": item.get("fileName"),
            "file_length": item.get("fileLength"),
            "release_type": item.get("releaseType"),
            "game_versions": item.get("gameVersions", []),
            "download_url": item.get("downloadUrl"),
        }
        for item in payload.get("data", [])
    ]


async def get_file(mod_id: int, file_id: int) -> dict[str, Any] | None:
    """Fetch one exact CurseForge file by project and file ID."""
    if mod_id <= 0 or file_id <= 0:
        raise ValueError("Invalid CurseForge project or file ID.")
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=_headers()) as client:
        response = await client.get(f"{API}/mods/{mod_id}/files/{file_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        item = response.json().get("data") or {}
    if not item:
        return None
    return {
        "id": item.get("id"),
        "display_name": item.get("displayName"),
        "file_name": item.get("fileName"),
        "file_length": item.get("fileLength"),
        "release_type": item.get("releaseType"),
        "game_versions": item.get("gameVersions", []),
        "download_url": item.get("downloadUrl"),
    }
