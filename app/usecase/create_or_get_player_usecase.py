from __future__ import annotations

from app.domain.exceptions import PlayerAlreadyExistsError, PlayerNotFoundError
from app.domain.player import Player
from app.domain.ports.player_repository import PlayerRepository
from app.domain.pseudo import normalize_and_validate


class CreateOrGetPlayerUseCase:
    """Upsert idempotent par pseudo.

    Deux appels `POST /players` avec le même pseudo renvoient le même Player
    (même id, même created_at). Le pseudo est normalisé avant la recherche pour
    que `abc`, `ABC` et `abc#hetic` convergent tous vers la même ligne.
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
            # Race : un autre appelant a inséré le même pseudo entre notre
            # SELECT et notre INSERT — on re-fetch la ligne gagnante.
            recovered = await self._repository.get_by_pseudo(pseudo)
            if recovered is None:
                raise PlayerNotFoundError(
                    f"Player {pseudo!r} reported as duplicate but cannot be re-fetched"
                )
            return recovered
