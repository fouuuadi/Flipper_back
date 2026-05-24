from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.exceptions import SessionNotFoundError
from app.domain.game import GameMode
from app.domain.ports.event_buffer import EventBuffer
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.player_repository import PlayerRepository
from app.domain.ports.session_store import SessionStore


@dataclass
class FinishAndPersistResult:
    player_id: int
    game_id: int
    final_score: int
    event_count: int
    improved: bool | None
    previous_best: int | None


class FinishAndPersistUseCase:
    """End-of-game flush: Redis session + event buffer → MySQL atomic insert.

    This is the **only** code path that writes the persistent DB during a
    game's lifecycle. Everything else stays in Redis.

    In solo mode, the use case also computes whether the new score beats the
    player's best score so far (`improved`, with `previous_best` as the
    reference). In 1v1 the notion of personal record doesn't apply, so
    `improved` is set to `None`.
    """

    def __init__(
        self,
        session_store: SessionStore,
        event_buffer: EventBuffer,
        game_repository: GameRepository,
        player_repository: PlayerRepository,
    ):
        self._session_store = session_store
        self._event_buffer = event_buffer
        self._game_repository = game_repository
        self._player_repository = player_repository

    async def execute(self, session_id: str) -> FinishAndPersistResult:
        session = await self._session_store.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} not found")

        events = await self._event_buffer.read_all(session_id)
        finished_at = datetime.now(timezone.utc)

        previous_best = await self._previous_best_for(session.pseudo, session.mode)

        player_id, game_id, event_count = await self._game_repository.persist_finished_session(
            pseudo=session.pseudo,
            mode=session.mode,
            score=session.score,
            started_at=session.created_at,
            finished_at=finished_at,
            events=events,
        )

        improved = self._compute_improved(session.mode, session.score, previous_best)

        # DB transaction has committed — safe to delete Redis state now.
        await self._event_buffer.clear(session_id)
        await self._session_store.delete(session_id)

        return FinishAndPersistResult(
            player_id=player_id,
            game_id=game_id,
            final_score=session.score,
            event_count=event_count,
            improved=improved,
            previous_best=previous_best,
        )

    async def _previous_best_for(self, pseudo: str, mode: GameMode) -> int | None:
        if mode is not GameMode.SOLO:
            return None
        existing = await self._player_repository.get_by_pseudo(pseudo)
        if existing is None or existing.id is None:
            return None
        return await self._game_repository.get_best_solo_score(existing.id)

    @staticmethod
    def _compute_improved(
        mode: GameMode,
        new_score: int,
        previous_best: int | None,
    ) -> bool | None:
        if mode is not GameMode.SOLO:
            return None  # "improved" is meaningless in 1v1 — each match is unique
        if previous_best is None:
            return True  # first ever solo run for this player → counts as an improvement
        return new_score > previous_best
