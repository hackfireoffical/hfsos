"""GitHub repository and release metadata provider."""
from __future__ import annotations

import os
from typing import Any

import httpx

API = "https://api.github.com"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "HackFire-Gateway/0.1",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def search_repositories(query: str, limit: int = 10) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []
    params = {"q": query, "per_page": max(1, min(limit, 30)), "sort": "stars"}
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=_headers()) as client:
        response = await client.get(f"{API}/search/repositories", params=params)
        response.raise_for_status()
        payload = response.json()
    return [
        {
            "id": item["id"],
            "full_name": item["full_name"],
            "description": item.get("description"),
            "stars": item.get("stargazers_count", 0),
            "language": item.get("language"),
            "url": item["html_url"],
            "default_branch": item.get("default_branch"),
        }
        for item in payload.get("items", [])
    ]


async def latest_release(owner: str, repo: str) -> dict[str, Any] | None:
    owner, repo = owner.strip(), repo.strip()
    if not owner or not repo or "/" in owner or "/" in repo:
        raise ValueError("Provide owner and repository separately.")
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=_headers()) as client:
        response = await client.get(f"{API}/repos/{owner}/{repo}/releases/latest")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        item = response.json()
    return {
        "tag": item.get("tag_name"),
        "name": item.get("name"),
        "published_at": item.get("published_at"),
        "url": item.get("html_url"),
        "assets": [
            {
                "name": asset.get("name"),
                "size": asset.get("size"),
                "download_url": asset.get("browser_download_url"),
                "content_type": asset.get("content_type"),
            }
            for asset in item.get("assets", [])
        ],
    }
