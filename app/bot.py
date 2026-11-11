"""Run HackFire Gateway using Rubika long polling."""
from __future__ import annotations

import asyncio
import logging
import os

from app.rubika.client import RubikaClient
from app.rubika.handlers import handle_update

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("hackfire.bot")


async def run() -> None:
    client = RubikaClient()
    offset_id: str | None = None
    try:
        bot_info = await client.get_me()
        logger.info("Connected to Rubika Bot API.")
        while True:
            try:
                page = await client.get_updates(offset_id=offset_id, limit=20)
                updates = page.get("updates") or []
                for update in updates:
                    try:
                        await handle_update(client, update)
                    except Exception:
                        logger.exception("Failed to process a Rubika update.")
                offset_id = page.get("next_offset_id") or offset_id
                if not updates:
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Rubika polling error: %s", type(exc).__name__)
                await asyncio.sleep(5)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run())
