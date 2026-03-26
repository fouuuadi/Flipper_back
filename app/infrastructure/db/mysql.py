from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import aiomysql

logger = logging.getLogger(__name__)

pool: Optional[aiomysql.Pool] = None


async def connect(max_retries: int = 10, retry_delay: float = 3.0) -> aiomysql.Pool:
    global pool

    for attempt in range(1, max_retries + 1):
        try:
            pool = await aiomysql.create_pool(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "3306")),
                db=os.getenv("DB_NAME", "flipper"),
                user=os.getenv("DB_USER", "flipper_user"),
                password=os.getenv("DB_PASSWORD", "flipper_password"),
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
