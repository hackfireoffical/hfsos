"""Modrinth project and version metadata provider."""
from __future__ import annotations

from typing import Any

import httpx

API = "https://api.modrinth.com/v2"
HEADERS = {"User-Agent": "HackFireGateway/0.1 (contact: admin)"}
TIMEOUT = httpx.Timeout(15.0, connect=5.0)


async def search_projects(
    query: str,
    project_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []
    params: dict[str, Any] = {"query": query, "limit": max(1, min(limit, 30))}
    if project_type in {"mod", "modpack", "resourcepack", "shader"}:
        params["facets"] = f'[["project_type:{project_type}"]]'
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        response = await client.get(f"{API}/search", params=params)
        response.raise_for_status()
        payload = response.json()
    return [
        {
            "project_id": item.get("project_id"),
            "slug": item.get("slug"),
            "title": item.get("title"),
            "description": item.get("description"),
            "project_type": item.get("project_type"),
            "downloads": item.get("downloads", 0),
            "icon_url": item.get("icon_url"),
            "url": f"https://modrinth.com/{item.get('project_type', 'mod')}/{item.get('slug')}",
        }
        for item in payload.get("hits", [])
    ]


async def project_versions(
    project_id_or_slug: str,
    game_version: str | None = None,
    loader: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    identifier = project_id_or_slug.strip()
    if not identifier or "/" in identifier:
        raise ValueError("Provide a Modrinth project ID or slug.")
    params: dict[str, Any] = {"limit": max(1, min(limit, 50))}
    if game_version:
        params["game_versions"] = f'["{game_version}"]'
    if loader in {"fabric", "forge", "neoforge", "quilt"}:
        params["loaders"] = f'["{loader}"]'
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        response = await client.get(f"{API}/project/{identifier}/version", params=params)
        response.raise_for_status()
        payload = response.json()
    return [
        {
            "version_id": item.get("id"),
            "name": item.get("name"),
            "version_number": item.get("version_number"),
            "game_versions": item.get("game_versions", []),
            "loaders": item.get("loaders", []),
            "date_published": item.get("date_published"),
            "files": [
                {
                    "filename": file.get("filename"),
                    "size": file.get("size"),
                    "url": file.get("url"),
                    "primary": file.get("primary", False),
                    "sha512": file.get("hashes", {}).get("sha512"),
                }
                for file in item.get("files", [])
            ],
        }
        for item in payload
    ]
