from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from app.domain.ports.event_buffer import EventBuffer

EVENT_BUFFER_KEY_PREFIX = "events:"


def _key(session_id: str) -> str:
    return f"{EVENT_BUFFER_KEY_PREFIX}{session_id}"


class RedisEventBuffer(EventBuffer):
    """Redis-backed event buffer using a per-session LIST.

    Events are RPUSH'd as JSON strings (preserving order). `read_all` returns
    them in arrival order. The list shares the same sliding TTL semantics as
    the session Hash so it expires naturally if the session is abandoned.
    """

    def __init__(self, redis: Redis, ttl_seconds: int):
        self._redis = redis
        self._ttl = ttl_seconds

    async def push(self, session_id: str, event: dict[str, Any]) -> None:
        key = _key(session_id)
        await self._redis.rpush(key, json.dumps(event))
        await self._redis.expire(key, self._ttl)

    async def read_all(self, session_id: str) -> list[dict[str, Any]]:
        key = _key(session_id)
        raw_events = await self._redis.lrange(key, 0, -1)
        return [json.loads(raw) for raw in raw_events]

    async def clear(self, session_id: str) -> None:
        await self._redis.delete(_key(session_id))
