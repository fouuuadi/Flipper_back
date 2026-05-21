from __future__ import annotations

import asyncio
import logging
from typing import Optional

import aiomysql

from app.config import Settings

logger = logging.getLogger(__name__)

pool: Optional[aiomysql.Pool] = None


async def connect(
    settings: Settings,
    max_retries: int = 10,
    retry_delay: float = 3.0,
) -> aiomysql.Pool:
    global pool

    for attempt in range(1, max_retries + 1):
        try:
            pool = await aiomysql.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                db=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                autocommit=True,
            )
            logger.info("Connected to MySQL (attempt %d/%d)", attempt, max_retries)
            return pool
        except Exception as e:
            logger.warning("MySQL connection failed (attempt %d/%d): %s", attempt, max_retries, e)
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)

    raise RuntimeError(f"Could not connect to MySQL after {max_retries} attempts")


async def disconnect():
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        pool = None
        logger.info("Disconnected from MySQL")


def get_pool() -> aiomysql.Pool:
    if pool is None:
        raise RuntimeError("Database pool not initialized. Call connect() first.")
    return pool
