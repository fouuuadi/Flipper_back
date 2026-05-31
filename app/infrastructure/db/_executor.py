from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Union

import asyncpg

Executor = Union[asyncpg.Pool, asyncpg.Connection]


@asynccontextmanager
async def acquire(executor: Executor) -> AsyncIterator[asyncpg.Connection]:
    """Yield a connection from either a pool or an already-acquired connection.

    Lets a single repository run standalone (pool) or inside a Unit of Work
    (a connection shared across repos under one transaction) with no change
    to the SQL call sites.
    """
    if isinstance(executor, asyncpg.Pool):
        async with executor.acquire() as conn:
            yield conn
        return
    yield executor
