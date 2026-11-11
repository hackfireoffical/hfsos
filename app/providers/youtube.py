"""YouTube search metadata using official API and the complete public fallback lists."""
from __future__ import annotations
import asyncio
import os
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse
import httpx

TIMEOUT = httpx.Timeout(12.0, connect=4.0)
UA = "HackFireGateway/1.0"
INSTANCE_CONCURRENCY = 8


def _https_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and parsed.hostname else None


async def _official_search(query: str, limit: int) -> list[dict[str, Any]]:
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YouTube Data API key is not configured")
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": UA}) as client:
        response = await client.get("https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "type": "video", "q": query, "maxResults": limit, "key": key})
        response.raise_for_status()
        payload = response.json()
    return [{
        "provider": "youtube-data-api",
        "video_id": item.get("id", {}).get("videoId"),
        "title": item.get("snippet", {}).get("title"),
        "description": item.get("snippet", {}).get("description"),
        "channel": item.get("snippet", {}).get("channelTitle"),
        "published_at": item.get("snippet", {}).get("publishedAt"),
        "url": f"https://www.youtube.com/watch?v={item.get('id', {}).get('videoId')}",
    } for item in payload.get("items", []) if item.get("id", {}).get("videoId")]


async def _invidious_instances(client: httpx.AsyncClient) -> list[str]:
    response = await client.get("https://api.invidious.io/instances.json", params={"sort_by": "health"})
    response.raise_for_status()
    urls, seen = [], set()
    for entry in response.json():
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        candidate = _https_url(entry[0])
        metadata = entry[1]
        if candidate and isinstance(metadata, dict) and metadata.get("api") and candidate not in seen:
            urls.append(candidate)
            seen.add(candidate)
    return urls


async def _first_success(instances: list[str], search_instance: Callable[[str], Awaitable[list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(INSTANCE_CONCURRENCY)
    async def run(base: str) -> list[dict[str, Any]]:
        async with semaphore:
            try:
                return await search_instance(base)
            except (httpx.HTTPError, ValueError, TypeError, KeyError):
                return []
    tasks = [asyncio.create_task(run(base)) for base in instances]
    try:
        for pending in asyncio.as_completed(tasks):
            results = await pending
            if results:
                return results
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    raise RuntimeError("No discovered instance returned search results")


async def _search_invidious(query: str, limit: int) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": UA}, follow_redirects=True) as client:
        instances = await _invidious_instances(client)
        async def search_instance(base: str) -> list[dict[str, Any]]:
            response = await client.get(f"{base}/api/v1/search", params={"q": query, "type": "video"})
            response.raise_for_status()
            return [{
                "provider": "invidious", "video_id": item.get("videoId"),
                "title": item.get("title"), "description": item.get("description"),
                "channel": item.get("author"), "duration": item.get("lengthSeconds"),
                "url": f"https://www.youtube.com/watch?v={item.get('videoId')}",
            } for item in response.json() if isinstance(item, dict) and item.get("type") == "video" and item.get("videoId")][:limit]
        return await _first_success(instances, search_instance)


async def _piped_instances(client: httpx.AsyncClient) -> list[str]:
    response = await client.get("https://piped-instances.kavin.rocks/")
    response.raise_for_status()
    urls, seen = [], set()
    for item in response.json() if isinstance(response.json(), list) else []:
        candidate = _https_url(item.get("api_url")) if isinstance(item, dict) and item.get("is_api") else None
        if candidate and candidate not in seen:
            urls.append(candidate)
            seen.add(candidate)
    return urls


async def _search_piped(query: str, limit: int) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": UA}, follow_redirects=True) as client:
        instances = await _piped_instances(client)
        async def search_instance(base: str) -> list[dict[str, Any]]:
            response = await client.get(f"{base}/search", params={"q": query, "filter": "videos"})
            response.raise_for_status()
            return [{
                "provider": "piped", "video_id": item.get("url", "").split("v=")[-1].split("&")[0],
                "title": item.get("title"), "channel": item.get("uploaderName"),
                "duration": item.get("duration"), "url": item.get("url"),
            } for item in response.json() if isinstance(item, dict) and item.get("url")][:limit]
        return await _first_success(instances, search_instance)


async def search_videos(query: str, limit: int = 10) -> dict[str, Any]:
    query = query.strip()
    if not query:
        return {"provider": None, "results": []}
    limit = max(1, min(limit, 20))
    errors = []
    for provider in (_official_search, _search_invidious, _search_piped):
        try:
            results = await provider(query, limit)
            return {"provider": results[0]["provider"] if results else None, "results": results, "fallback_errors": errors}
        except Exception as exc:
            errors.append(f"{provider.__name__}: {type(exc).__name__}")
    raise RuntimeError("All YouTube search providers failed: " + "; ".join(errors))
