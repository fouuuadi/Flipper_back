from __future__ import annotations

import logging

from app.domain.ports.borne_store import BorneStore
from app.domain.ports.session_store import SessionStore
from app.usecase.apply_borne_intent_usecase import ApplyBorneIntentUseCase
from app.usecase.finish_borne_game_usecase import FinishBorneGameUseCase

logger = logging.getLogger(__name__)


class FinishBorneGameFromRelayUseCase:
    """Game over relayé par le playfield (autorité du score sur table virtuelle).

    La table étant simulée côté front, c'est le playfield qui calcule le score ;
    le backend ne reçoit que des relais. À la fin de partie, le playfield pousse
    un ``game:over`` avec le ``finalScore``. On l'écrit dans la session active de
    la borne, puis on délègue à {@link FinishBorneGameUseCase} qui bascule la nav
    en ``game_over`` et persiste le run en base — exactement comme la fin de
    partie naturelle (MQTT).
    """

    def __init__(
        self,
        borne_store: BorneStore,
        session_store: SessionStore,
        finish_borne_game: FinishBorneGameUseCase,
        apply_intent: ApplyBorneIntentUseCase,
    ):
        self._borne_store = borne_store
        self._session_store = session_store
        self._finish_borne_game = finish_borne_game
        self._apply_intent = apply_intent

    async def execute(self, borne_id: str, final_score: object) -> None:
        borne = await self._borne_store.get_or_create(borne_id)
        session_id = borne.active_session_id
        if session_id is None:
            # Pas de partie rattachée (ex. game over sans session) : on bascule
            # au moins la navigation, sans rien persister.
            await self._apply_intent.mark_game_over(borne_id)
            return

        session = await self._session_store.get(session_id)
        if session is not None and isinstance(final_score, int):
            session.score = final_score
            await self._session_store.update(session)

        await self._finish_borne_game.execute(session_id)
