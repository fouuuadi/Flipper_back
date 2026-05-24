from __future__ import annotations

import asyncio
import logging

import asyncpg

from app.config import Settings

logger = logging.getLogger(__name__)

pool: asyncpg.Pool | None = None


async def connect(
    settings: Settings,
    max_retries: int = 10,
    retry_delay: float = 3.0,
) -> asyncpg.Pool:
    global pool

    for attempt in range(1, max_retries + 1):
        try:
            pool = await asyncpg.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                min_size=1,
                max_size=10,
            )
            logger.info("Connected to PostgreSQL (attempt %d/%d)", attempt, max_retries)
            return pool
        except Exception as e:
            logger.warning(
                "PostgreSQL connection failed (attempt %d/%d): %s",
                attempt,
                max_retries,
                e,
            )
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)

    raise RuntimeError(f"Could not connect to PostgreSQL after {max_retries} attempts")


async def disconnect() -> None:
    global pool
    if pool:
        await pool.close()
        pool = None
        logger.info("Disconnected from PostgreSQL")


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database pool not initialized. Call connect() first.")
    return pool
