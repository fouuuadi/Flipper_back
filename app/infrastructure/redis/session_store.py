from __future__ import annotations

from datetime import datetime

from redis.asyncio import Redis

from app.domain.game import GameMode
from app.domain.ports.session_store import SessionStore
from app.domain.session import Session, SessionStatus

SESSION_KEY_PREFIX = "session:"


def _session_key(session_id: str) -> str:
    return f"{SESSION_KEY_PREFIX}{session_id}"


class RedisSessionStore(SessionStore):
    """Stocke les sessions de jeu en cours dans Redis (un hash par session).

    TTL glissant : chaque lecture ET écriture repousse l'expiration. Une session
    activement jouée ne meurt donc jamais, mais une session laissée à l'abandon
    (plus aucun accès) finit par expirer toute seule — pas de nettoyage manuel.
    """

    def __init__(self, redis: Redis, ttl_seconds: int):
        self._redis = redis
        self._ttl = ttl_seconds

    async def create(self, session: Session) -> None:
        key = _session_key(session.session_id)
        await self._redis.hset(key, mapping=self._to_hash(session))
        await self._redis.expire(key, self._ttl)

    async def get(self, session_id: str) -> Session | None:
        key = _session_key(session_id)
        data = await self._redis.hgetall(key)
        if not data:
            return None
        # TTL glissant : on repousse l'expiration à chaque lecture.
        await self._redis.expire(key, self._ttl)
        return self._from_hash(data)

    async def update(self, session: Session) -> None:
        key = _session_key(session.session_id)
        await self._redis.hset(key, mapping=self._to_hash(session))
        await self._redis.expire(key, self._ttl)

    async def delete(self, session_id: str) -> None:
        await self._redis.delete(_session_key(session_id))

    @staticmethod
    def _to_hash(session: Session) -> dict[str, str]:
        return {
            "session_id": session.session_id,
            "pseudo": session.pseudo,
            "score": str(session.score),
            "lives": str(session.lives),
            "combo": str(session.combo),
            "status": session.status.value,
            "mode": session.mode.value,
            "room_code": session.room_code or "",
            "created_at": session.created_at.isoformat(),
        }

    @staticmethod
    def _from_hash(data: dict[str, str]) -> Session:
        # Redis ne stocke que des chaînes : on reconstruit les types Python.
        # Les `.get(..., défaut)` couvrent les sessions écrites par une version
        # antérieure du schéma (champ ajouté depuis) au lieu de planter.
        # room_code : on a stocké "" pour le solo (cf. _to_hash), on le relit en None.
        return Session(
            session_id=data["session_id"],
            pseudo=data["pseudo"],
            score=int(data["score"]),
            lives=int(data.get("lives", 3)),
            combo=int(data.get("combo", 0)),
            status=SessionStatus(data["status"]),
            mode=GameMode(data.get("mode", GameMode.SOLO.value)),
            room_code=data.get("room_code") or None,
            created_at=datetime.fromisoformat(data["created_at"]),
        )
