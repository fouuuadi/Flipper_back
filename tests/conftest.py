"""Fixtures pytest partagées pour la suite de tests d'intégration.

Centralise le pattern pool asyncpg + truncation des tables pour que chaque
fichier de test n'ait plus à copier/coller le même boilerplate. Les tests
existants gardent leurs fixtures locales quand ils ont besoin d'un scope
différent ou d'un câblage supplémentaire (par ex. appeler `di.set_db_pool`
sur l'app FastAPI).
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
    """Construit un pool asyncpg à partir des variables d'env DB_* standard."""
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
