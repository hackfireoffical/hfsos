"""Bounded downloads from supported provider asset URLs and Rubika delivery."""
from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

CHUNK_SIZE = 1024 * 1024
RUBIKA_FILE_LIMIT = 50_000_000
DELIVERY_PART_SIZE = 45 * 1024 * 1024
ALLOWED_HOSTS = (
    "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",
    "githubusercontent.com", "modrinth.com", "cdn.modrinth.com", "cdn-raw.modrinth.com",
    "forgecdn.net", "curseforge.com",
)


class DownloadError(RuntimeError):
    pass


def safe_filename(name: str) -> str:
    name = Path(name or "download.bin").name
    name = re.sub(r"[^A-Za-z0-9._() -]", "_", name).strip(" .")
    return (name or "download.bin")[:180]


def is_allowed_asset_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    return parsed.scheme == "https" and any(host == item or host.endswith("." + item) for item in ALLOWED_HOSTS)


async def download_asset(url: str, filename: str, expected_sha512: str | None = None) -> Path:
    """Stream a provider-returned asset to disk, enforcing HTTPS, host and size limits."""
    if not is_allowed_asset_url(url):
        raise DownloadError("The provider returned an unsupported download host.")
    root = Path(os.getenv("DOWNLOAD_DIR", "data/downloads")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    job_dir = root / uuid.uuid4().hex
    job_dir.mkdir(mode=0o700)
    target = job_dir / safe_filename(filename)
    temporary = target.with_suffix(target.suffix + ".part")
    max_bytes = max(1, int(os.getenv("MAX_DOWNLOAD_SIZE_MB", "512"))) * 1024 * 1024
    digest = hashlib.sha512()
    total = 0
    timeout = httpx.Timeout(90.0, connect=15.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers={"User-Agent": "HackFireGateway/1.0"}) as client:
            current = url
            for redirect in range(6):
                if not is_allowed_asset_url(current):
                    raise DownloadError("A download redirect pointed to an unsupported host.")
                response = await client.send(client.build_request("GET", current), stream=True)
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    await response.aclose()
                    if not location:
                        raise DownloadError("The download server returned an invalid redirect.")
                    current = str(response.url.join(location))
                    continue
                response.raise_for_status()
                length = response.headers.get("content-length")
                if length and int(length) > max_bytes:
                    raise DownloadError(f"File exceeds the configured {max_bytes // (1024 * 1024)} MB download limit.")
                with temporary.open("wb") as output:
                    async for chunk in response.aiter_bytes(CHUNK_SIZE):
                        total += len(chunk)
                        if total > max_bytes:
                            raise DownloadError(f"File exceeds the configured {max_bytes // (1024 * 1024)} MB download limit.")
                        digest.update(chunk)
                        output.write(chunk)
                await response.aclose()
                break
            else:
                raise DownloadError("Too many download redirects.")
        if expected_sha512 and digest.hexdigest().lower() != expected_sha512.lower():
            raise DownloadError("Downloaded file failed the provider SHA-512 integrity check.")
        temporary.replace(target)
        return target
    except Exception:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        job_dir.rmdir()
        raise


def split_for_rubika(path: Path) -> list[Path]:
    """Return the original file or bounded 45 MiB pieces for Rubika's 50 MiB cap."""
    size = path.stat().st_size
    if size <= RUBIKA_FILE_LIMIT:
        return [path]
    parts: list[Path] = []
    try:
        with path.open("rb") as source:
            index = 1
            while True:
                data = source.read(DELIVERY_PART_SIZE)
                if not data:
                    break
                part = path.with_name(f"{path.name}.part{index:03d}")
                part.write_bytes(data)
                parts.append(part)
                index += 1
        return parts
    except Exception:
        for part in parts:
            part.unlink(missing_ok=True)
        raise

def cleanup_download_cache(max_age_seconds: int = 3600) -> int:
    """Delete abandoned UUID job directories older than the retention window.

    Completed deliveries are removed immediately by the handler. This sweep is
    a safety net for VPS restarts, forced termination, or interrupted uploads.
    """
    import shutil
    import time

    root = Path(os.getenv("DOWNLOAD_DIR", "data/downloads")).resolve()
    if not root.exists():
        return 0
    now = time.time()
    removed = 0
    for entry in root.iterdir():
        if not entry.is_dir() or not re.fullmatch(r"[0-9a-f]{32}", entry.name):
            continue
        try:
            if now - entry.stat().st_mtime >= max(60, max_age_seconds):
                shutil.rmtree(entry)
                removed += 1
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return removed


def cleanup_job_directory(path: Path | None) -> None:
    """Remove a completed download's private job directory immediately."""
    import shutil

    if path is None:
        return
    try:
        shutil.rmtree(path.parent)
    except FileNotFoundError:
        pass
