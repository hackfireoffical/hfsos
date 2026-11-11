"""YouTube search metadata with optional official API and public fallbacks.

This module returns search metadata only. It does not extract or download media.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

TIMEOUT = httpx.Timeout(12.0, connect=4.0)
UA = "HackFireGateway/0.1"


async def _official_search(query: str, limit: int) -> list[dict[str, Any]]:
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YouTube Data API key is not configured")
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": UA}) as client:
        response = await client.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "type": "video", "q": query, "maxResults": limit, "key": key},
        )
        response.raise_for_status()
        payload = response.json()
    return [
        {
            "provider": "youtube-data-api",
            "video_id": item.get("id", {}).get("videoId"),
            "title": item.get("snippet", {}).get("title"),
            "description": item.get("snippet", {}).get("description"),
            "channel": item.get("snippet", {}).get("channelTitle"),
            "published_at": item.get("snippet", {}).get("publishedAt"),
            "url": f"https://www.youtube.com/watch?v={item.get('id', {}).get('videoId')}",
        }
        for item in payload.get("items", [])
    ]


async def _invidious_instances(client: httpx.AsyncClient) -> list[str]:
    response = await client.get("https://api.invidious.io/instances.json", params={"sort_by": "health"})
    response.raise_for_status()
    entries = response.json()
    urls: list[str] = []
    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        url, metadata = entry[0], entry[1]
        if isinstance(url, str) and isinstance(metadata, dict) and metadata.get("api"):
            urls.append(url.rstrip("/"))
    return urls[:20]


async def _search_invidious(query: str, limit: int) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": UA}, follow_redirects=True) as client:
        instances = await _invidious_instances(client)
        for base in instances:
            try:
                response = await client.get(
                    f"{base}/api/v1/search",
                    params={"q": query, "type": "video"},
                )
                response.raise_for_status()
                payload = response.json()
                results = [
                    {
                        "provider": "invidious",
                        "video_id": item.get("videoId"),
                        "title": item.get("title"),
                        "description": item.get("description"),
                        "channel": item.get("author"),
                        "duration": item.get("lengthSeconds"),
                        "url": f"https://www.youtube.com/watch?v={item.get('videoId')}",
                    }
                    for item in payload
                    if item.get("type") == "video" and item.get("videoId")
                ]
                if results:
                    return results[:limit]
            except (httpx.HTTPError, ValueError, TypeError):
                continue
    raise RuntimeError("No healthy Invidious instance returned search results")


async def _piped_instances(client: httpx.AsyncClient) -> list[str]:
    response = await client.get("https://piped-instances.kavin.rocks/")
    response.raise_for_status()
    payload = response.json()
    urls: list[str] = []
    for item in payload if isinstance(payload, list) else []:
        if isinstance(item, dict) and item.get("api_url") and item.get("is_api"):
            urls.append(item["api_url"].rstrip("/"))
    return urls[:20]


async def _search_piped(query: str, limit: int) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": UA}, follow_redirects=True) as client:
        instances = await _piped_instances(client)
        for base in instances:
            try:
                response = await client.get(
                    f"{base}/search",
                    params={"q": query, "filter": "videos"},
                )
                response.raise_for_status()
                payload = response.json()
                results = [
                    {
                        "provider": "piped",
                        "video_id": item.get("url", "").split("v=")[-1],
                        "title": item.get("title"),
                        "channel": item.get("uploaderName"),
                        "duration": item.get("duration"),
                        "url": item.get("url"),
                    }
                    for item in payload
                    if isinstance(item, dict) and item.get("url")
                ]
                if results:
                    return results[:limit]
            except (httpx.HTTPError, ValueError, TypeError):
                continue
    raise RuntimeError("No healthy Piped instance returned search results")


async def search_videos(query: str, limit: int = 10) -> dict[str, Any]:
    query = query.strip()
    if not query:
        return {"provider": None, "results": []}
    limit = max(1, min(limit, 20))
    errors: list[str] = []
    for provider in (_official_search, _search_invidious, _search_piped):
        try:
            results = await provider(query, limit)
            return {"provider": results[0]["provider"] if results else None, "results": results, "fallback_errors": errors}
        except Exception as exc:
            errors.append(f"{provider.__name__}: {type(exc).__name__}")
    raise RuntimeError("All YouTube search providers failed: " + "; ".join(errors))
