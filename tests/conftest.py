"""Shared pytest fixtures for the integration test suite.

Centralises the asyncpg pool + table truncation pattern so every test file
no longer has to copy/paste the same boilerplate. Existing tests keep their
local fixtures when they need a different scope or extra wiring (e.g.
calling `di.set_db_pool` on the FastAPI app).
"""
from __future__ import annotations

import os

import asyncpg
import pytest_asyncio
from dotenv import load_dotenv

load_dotenv()

_TRUNCATE_SQL = "TRUNCATE game_events, games, rooms, players, matchmaking RESTART IDENTITY CASCADE"


def _db_host() -> str:
    host = os.getenv("DB_HOST", "localhost")
    return "localhost" if host == "db" else host


async def make_db_pool() -> asyncpg.Pool:
    """Build an asyncpg pool from the standard DB_* env vars."""
    return await asyncpg.create_pool(
        host=_db_host(),
        port=int(os.getenv("DB_PORT", 5432)),
        user=os.getenv("DB_USER", "flipper"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "flipper"),
        min_size=1,
        max_size=5,
    )


async def truncate_all(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(_TRUNCATE_SQL)


@pytest_asyncio.fixture
async def db_pool():
    pool = await make_db_pool()
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def clean_tables(db_pool):
    await truncate_all(db_pool)
    yield
