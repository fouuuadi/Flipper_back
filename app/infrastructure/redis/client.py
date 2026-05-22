from __future__ import annotations

import logging

from redis.asyncio import Redis, from_url

logger = logging.getLogger(__name__)


async def connect(url: str) -> Redis:
    client: Redis = from_url(url, encoding="utf-8", decode_responses=True)
    await client.ping()
    logger.info("Connected to Redis at %s", url)
    return client


async def disconnect(client: Redis) -> None:
    await client.aclose()
    logger.info("Disconnected from Redis")
