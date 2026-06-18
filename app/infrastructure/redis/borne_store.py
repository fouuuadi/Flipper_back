from __future__ import annotations

from redis.asyncio import Redis

from app.domain.borne import Borne, BorneNavState
from app.domain.ports.borne_store import BorneStore

BORNE_KEY_PREFIX = "borne:"


def _borne_key(borne_id: str) -> str:
    return f"{BORNE_KEY_PREFIX}{borne_id}"


class RedisBorneStore(BorneStore):
    """Stockage Redis de l'état borne.

    Contrairement aux sessions (qui ont un TTL glissant), la borne est
    **permanente** : aucune expiration, elle survit aux parties et aux
    redémarrages des écrans.
    """

    def __init__(self, redis: Redis):
        self._redis = redis

    async def get_or_create(self, borne_id: str) -> Borne:
        data = await self._redis.hgetall(_borne_key(borne_id))
        if data:
            return self._from_hash(data)
        borne = Borne(borne_id=borne_id)
        await self.update(borne)
        return borne

    async def update(self, borne: Borne) -> None:
        await self._redis.hset(_borne_key(borne.borne_id), mapping=self._to_hash(borne))

    @staticmethod
    def _to_hash(borne: Borne) -> dict[str, str]:
        return {
            "borne_id": borne.borne_id,
            "nav": borne.nav.value,
            "active_session_id": borne.active_session_id or "",
        }

    @staticmethod
    def _from_hash(data: dict[str, str]) -> Borne:
        return Borne(
            borne_id=data["borne_id"],
            nav=BorneNavState(data["nav"]),
            active_session_id=data.get("active_session_id") or None,
        )
