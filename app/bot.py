"""Run HackFire Gateway using Rubika long polling."""
from __future__ import annotations

import asyncio
import logging
import os

from app.downloads import cleanup_download_cache
from app.rubika.client import RubikaClient
from app.rubika.handlers import handle_update

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("hackfire.bot")
MAX_ACTIVE_HANDLERS = max(2, int(os.getenv("MAX_ACTIVE_HANDLERS", "8")))


async def run() -> None:
    removed = cleanup_download_cache()
    logger.info("Startup cleanup removed %d abandoned download job(s).", removed)
    client = RubikaClient()
    offset_id: str | None = None
    handler_slots = asyncio.Semaphore(MAX_ACTIVE_HANDLERS)
    pending: set[asyncio.Task] = set()

    async def dispatch(update: dict) -> None:
        async with handler_slots:
            try:
                await handle_update(client, update)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Failed to process a Rubika update.")

    try:
        await client.get_me()
        logger.info("Connected to Rubika Bot API.")
        while True:
            try:
                page = await client.get_updates(offset_id=offset_id, limit=20)
                updates = page.get("updates") or []
                for update in updates:
                    task = asyncio.create_task(dispatch(update))
                    pending.add(task)
                    task.add_done_callback(pending.discard)
                offset_id = page.get("next_offset_id") or offset_id
                if not updates:
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Rubika polling error: %s", type(exc).__name__)
                await asyncio.sleep(5)
    finally:
        for task in list(pending):
            task.cancel()
        if pending:
            await asyncio.gather(*list(pending), return_exceptions=True)
        await client.close()


if __name__ == "__main__":
    asyncio.run(run())
