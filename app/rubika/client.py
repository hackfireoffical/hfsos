"""Small async client for the official Rubika Bot API v3."""
from __future__ import annotations

import os
from typing import Any

import httpx


class RubikaAPIError(RuntimeError):
    pass


class RubikaClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.getenv("RUBIKA_BOT_TOKEN", "")
        if not self.token:
            raise ValueError("RUBIKA_BOT_TOKEN is not configured")
        self.base_url = f"https://botapi.rubika.ir/v3/{self.token}"
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=8.0))

    async def close(self) -> None:
        await self.client.aclose()

    async def call(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self.client.post(f"{self.base_url}/{method}", json=payload or {})
        response.raise_for_status()
        body = response.json()
        if body.get("status") != "OK":
            # Do not include request URL: it contains the bot token.
            raise RubikaAPIError(f"Rubika API returned status {body.get('status')!r}")
        return body.get("data") or {}

    async def get_me(self) -> dict[str, Any]:
        return await self.call("getMe")

    async def get_updates(self, offset_id: str | None = None, limit: int = 20) -> dict[str, Any]:
        payload: dict[str, Any] = {"limit": max(1, min(limit, 100))}
        if offset_id:
            payload["offset_id"] = offset_id
        return await self.call("getUpdates", payload)

    async def send_message(
        self,
        chat_id: str,
        text: str,
        inline_keypad: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if inline_keypad:
            payload["inline_keypad"] = inline_keypad
        return await self.call("sendMessage", payload)

    async def send_file(self, chat_id: str, path: Path, text: str | None = None) -> dict[str, Any]:
        """Upload one Rubika-safe file and send it to a chat using Bot API v3."""
        if path.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("Rubika general-file uploads are limited to 50 MB.")
        requested = await self.call("requestSendFile", {"type": "File"})
        upload_url = requested.get("upload_url")
        if not isinstance(upload_url, str) or not upload_url.startswith("https://"):
            raise RubikaAPIError("Rubika returned an invalid upload URL.")
        with path.open("rb") as handle:
            response = await self.client.post(
                upload_url,
                files={"file": (path.name, handle, "application/octet-stream")},
                timeout=httpx.Timeout(180.0, connect=15.0),
            )
        response.raise_for_status()
        uploaded = response.json()
        if uploaded.get("status") != "OK":
            raise RubikaAPIError("Rubika file upload failed.")
        file_id = (uploaded.get("data") or {}).get("file_id")
        if not file_id:
            raise RubikaAPIError("Rubika upload response did not contain a file ID.")
        payload: dict[str, Any] = {"chat_id": chat_id, "file_id": file_id}
        if text:
            payload["text"] = text[:1000]
        return await self.call("sendFile", payload)
