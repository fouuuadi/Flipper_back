from __future__ import annotations

from redis.asyncio import Redis

from app.domain.ports.session_service import SessionService
from app.infrastructure.redis.session_store import SESSION_KEY_PREFIX


class RedisSessionService(SessionService):
    """Vérifie l'unicité d'un pseudo dans une room en scannant les sessions Redis actives."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def check_pseudo_uniqueness_in_room(self, room_code: str, pseudo: str) -> bool:
        """Retourne True si le pseudo est libre dans la room, False si déjà pris."""
        async for key in self._redis.scan_iter(match=f"{SESSION_KEY_PREFIX}*"):
            stored_room, stored_pseudo, stored_status = await self._redis.hmget(
                key, "room_code", "pseudo", "status"
            )
            if (
                stored_room == room_code
                and stored_pseudo == pseudo
                and stored_status != "over"
            ):
                return False
        return True
