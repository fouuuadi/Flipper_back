from __future__ import annotations

from app.domain.exceptions import PlayerAlreadyExistsError, PlayerNotFoundError
from app.domain.player import Player
from app.domain.ports.player_repository import PlayerRepository
from app.domain.pseudo import normalize_and_validate


class CreateOrGetPlayerUseCase:
    """Idempotent upsert by pseudo.

    Two `POST /players` calls with the same pseudo return the same Player
    (same id, same created_at). The pseudo is normalised before lookup so
    `abc`, `ABC`, and `abc#hetic` all converge on the same row.
    """

    def __init__(self, player_repository: PlayerRepository):
        self._repository = player_repository

    async def execute(self, raw_pseudo: str) -> Player:
        pseudo = normalize_and_validate(raw_pseudo)

        existing = await self._repository.get_by_pseudo(pseudo)
        if existing is not None:
            return existing

        try:
            return await self._repository.create(pseudo)
        except PlayerAlreadyExistsError:
            # Race: another caller inserted the same pseudo between our
            # SELECT and INSERT — re-fetch the winning row.
            recovered = await self._repository.get_by_pseudo(pseudo)
            if recovered is None:
                raise PlayerNotFoundError(
                    f"Player {pseudo!r} reported as duplicate but cannot be re-fetched"
                )
            return recovered
