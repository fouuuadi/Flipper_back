from __future__ import annotations

import logging

from app.domain.exceptions import SessionNotFoundError
from app.domain.ports.borne_store import BorneStore
from app.usecase.apply_borne_intent_usecase import ApplyBorneIntentUseCase
from app.usecase.finish_and_persist_usecase import FinishAndPersistUseCase

logger = logging.getLogger(__name__)


class FinishBorneGameUseCase:
    """Fin de partie naturelle (MQTT `flipper/game/over`) d'une session de borne.

    Bascule la navigation borne en `game_over` et **persiste automatiquement**
    le run en base. C'est ce qui remplace le `POST /scores` déclenché par le
    front (le front devenant un simple afficheur).

    No-op si la session terminée n'est **pas** celle rattachée à la borne : il
    s'agit alors d'une session legacy (créée par `POST /sessions`), dont la
    persistance reste pilotée par `POST /scores`. Ce garde-fou évite la double
    écriture pendant la migration du front.
    """

    def __init__(
        self,
        borne_store: BorneStore,
        borne_id: str,
        apply_intent: ApplyBorneIntentUseCase,
        finish_and_persist: FinishAndPersistUseCase,
    ):
        self._borne_store = borne_store
        self._borne_id = borne_id
        self._apply_intent = apply_intent
        self._finish_and_persist = finish_and_persist

    async def execute(self, session_id: str) -> None:
        borne = await self._borne_store.get_or_create(self._borne_id)
        if borne.active_session_id != session_id:
            logger.debug(
                "game over for session %s not attached to borne %s — leaving "
                "persistence to POST /scores",
                session_id,
                self._borne_id,
            )
            return

        await self._apply_intent.mark_game_over(self._borne_id)
        try:
            await self._finish_and_persist.execute(session_id)
        except SessionNotFoundError:
            logger.warning(
                "game over: session %s already gone before persistence", session_id
            )
