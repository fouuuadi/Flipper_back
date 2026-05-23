from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.exceptions import SessionNotFoundError
from app.domain.ports.event_buffer import EventBuffer
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.session_store import SessionStore


@dataclass
class FinishAndPersistResult:
    player_id: int
    game_id: int
    final_score: int
    event_count: int


class FinishAndPersistUseCase:
    """End-of-game flush: Redis session + event buffer → MySQL atomic insert.

    This is the **only** code path that writes the persistent DB during a
    game's lifecycle. Everything else stays in Redis.
    """

    def __init__(
        self,
        session_store: SessionStore,
        event_buffer: EventBuffer,
        game_repository: GameRepository,
    ):
        self._session_store = session_store
        self._event_buffer = event_buffer
        self._game_repository = game_repository

    async def execute(self, session_id: str) -> FinishAndPersistResult:
        session = await self._session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} not found")

        events = await self._event_buffer.read_all(session_id)
        finished_at = datetime.now(timezone.utc)

        player_id, game_id, event_count = await self._game_repository.persist_finished_session(
            pseudo=session.pseudo,
            mode=session.mode,
            score=session.score,
            started_at=session.created_at,
            finished_at=finished_at,
            events=events,
        )

        # DB transaction has committed — safe to delete Redis state now.
        await self._event_buffer.clear(session_id)
        await self._session_store.delete(session_id)

        return FinishAndPersistResult(
            player_id=player_id,
            game_id=game_id,
            final_score=session.score,
            event_count=event_count,
        )
