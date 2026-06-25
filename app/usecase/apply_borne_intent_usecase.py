from __future__ import annotations

import logging

from app.domain.borne import Borne, BorneNavState
from app.domain.game import GameMode
from app.domain.ports.borne_event_broadcaster import BorneEventBroadcaster
from app.domain.ports.borne_store import BorneStore
from app.domain.ports.session_store import SessionStore
from app.usecase.abandon_session_usecase import AbandonSessionUseCase
from app.usecase.create_session_usecase import CreateSessionUseCase
from app.usecase.pause_session_usecase import PauseSessionUseCase
from app.usecase.ready_up_usecase import ReadyUpUseCase
from app.usecase.resume_session_usecase import ResumeSessionUseCase
from app.usecase.start_countdown_usecase import StartCountdownUseCase

logger = logging.getLogger(__name__)

CMD_PAUSE = "cmd:pause"
CMD_RESUME = "cmd:resume"
CMD_ABANDON = "cmd:abandon"

_PLAYERS_VALIDATED = "PLAYERS_VALIDATED"


# Table de navigation, portée depuis le front (`src/core/gameMachine.ts`). Le
# backend en est désormais le seul décideur : chaque écran envoie un `intent`,
# le backend applique la transition et rebroadcast le `nav:state` aux 3 écrans.
#
# `PLAYERS_VALIDATED` (création de session) et le retour `game_over` ne sont pas
# de simples transitions : ils portent des effets de bord traités séparément.
_NAV_TRANSITIONS: dict[tuple[BorneNavState, str], BorneNavState] = {
    (BorneNavState.SPLASH, "PRESS_A"): BorneNavState.MENU,
    (BorneNavState.MENU, "START_GAME"): BorneNavState.IDENTIFICATION,
    (BorneNavState.MENU, "OPEN_LEADERBOARD"): BorneNavState.LEADERBOARD,
    (BorneNavState.MENU, "OPEN_BOUTIQUE"): BorneNavState.BOUTIQUE,
    (BorneNavState.MENU, "OPEN_SETTINGS"): BorneNavState.SETTINGS,
    (BorneNavState.IDENTIFICATION, "BACK_TO_MENU"): BorneNavState.MENU,
    (BorneNavState.BOUTIQUE, "START_GAME"): BorneNavState.IDENTIFICATION,
    (BorneNavState.BOUTIQUE, "BACK_TO_MENU"): BorneNavState.MENU,
    (BorneNavState.LEADERBOARD, "BACK_TO_MENU"): BorneNavState.MENU,
    (BorneNavState.SETTINGS, "BACK_TO_MENU"): BorneNavState.MENU,
    (BorneNavState.GAME_OVER, "REPLAY"): BorneNavState.IDENTIFICATION,
    (BorneNavState.GAME_OVER, "OPEN_LEADERBOARD"): BorneNavState.LEADERBOARD,
    (BorneNavState.GAME_OVER, "BACK_TO_MENU"): BorneNavState.MENU,
}


def next_nav_state(current: BorneNavState, action: str) -> BorneNavState | None:
    """Retourne l'état de navigation cible, ou None si l'action est invalide ici."""
    return _NAV_TRANSITIONS.get((current, action))


class ApplyBorneIntentUseCase:
    """Orchestrateur de tous les messages reçus sur le socket borne.

    - `intent` de navigation → applique la transition, persiste, rebroadcast
      `nav:state` aux 3 écrans.
    - `PLAYERS_VALIDATED` → crée la session de jeu côté backend, la rattache à
      la borne (`nav = in_game`), puis enchaîne ready + countdown sur le bus
      borne (les use cases de match émettent via le broadcaster borne).
    - `cmd:pause` / `cmd:resume` / `cmd:abandon` → pilotent la session active.
    """

    def __init__(
        self,
        borne_store: BorneStore,
        broadcaster: BorneEventBroadcaster,
        session_store: SessionStore,
    ):
        self._borne_store = borne_store
        self._broadcaster = broadcaster
        self._session_store = session_store

    # --- intents de navigation -------------------------------------------------

    async def execute(
        self, borne_id: str, action: str, payload: dict | None = None
    ) -> None:
        borne = await self._borne_store.get_or_create(borne_id)

        if action == _PLAYERS_VALIDATED:
            await self._start_game(borne, payload)
            return

        target = next_nav_state(borne.nav, action)
        if target is None:
            logger.debug(
                "intent %r ignored in nav=%s (borne %s)",
                action,
                borne.nav.value,
                borne_id,
            )
            return

        # Quitter `game_over` vers la navigation libère la session terminée.
        if borne.nav is BorneNavState.GAME_OVER and target in (
            BorneNavState.MENU,
            BorneNavState.IDENTIFICATION,
        ):
            borne.active_session_id = None

        borne.nav = target
        await self._borne_store.update(borne)
        await self._broadcast_nav(borne)

    # --- démarrage d'une partie ------------------------------------------------

    async def _start_game(self, borne: Borne, payload: dict | None) -> None:
        if borne.nav is not BorneNavState.IDENTIFICATION:
            logger.debug(
                "PLAYERS_VALIDATED ignored in nav=%s (borne %s)",
                borne.nav.value,
                borne.borne_id,
            )
            return

        pseudo = self._extract_pseudo(payload)
        if pseudo is None:
            logger.warning(
                "PLAYERS_VALIDATED without a pseudo (borne %s): %r",
                borne.borne_id,
                payload,
            )
            return
        mode = self._extract_mode(payload)

        session = await CreateSessionUseCase(self._session_store).execute(pseudo, mode)

        borne.active_session_id = session.session_id
        borne.nav = BorneNavState.IN_GAME
        await self._borne_store.update(borne)
        await self._broadcast_nav(borne)

        # Ready + countdown sur le bus borne : le broadcaster borne ignore le
        # session_id et diffuse aux 3 écrans (cf. BorneHubManager).
        countdown = StartCountdownUseCase(self._session_store, self._broadcaster)
        await ReadyUpUseCase(
            self._session_store, self._broadcaster, on_ready=countdown.execute
        ).execute(session.session_id)

    # --- contrôles de match (relayés depuis n'importe quel écran) --------------

    async def handle_match_command(self, borne_id: str, cmd_type: str) -> None:
        borne = await self._borne_store.get_or_create(borne_id)
        session_id = borne.active_session_id
        if session_id is None:
            logger.warning("%s on borne %s without an active session", cmd_type, borne_id)
            return

        if cmd_type == CMD_PAUSE:
            await PauseSessionUseCase(self._session_store, self._broadcaster).execute(
                session_id
            )
        elif cmd_type == CMD_RESUME:
            countdown = StartCountdownUseCase(self._session_store, self._broadcaster)
            await ResumeSessionUseCase(
                self._session_store, self._broadcaster, start_countdown=countdown.execute
            ).execute(session_id)
        elif cmd_type == CMD_ABANDON:
            await AbandonSessionUseCase(self._session_store, self._broadcaster).execute(
                session_id
            )
            await self.mark_game_over(borne_id)

    async def mark_game_over(self, borne_id: str) -> None:
        """Bascule la navigation en `game_over` quand la partie se termine.

        Réutilisé par l'abandon (ci-dessus) et par le game over naturel côté
        MQTT (#130). La session reste rattachée (`active_session_id`) jusqu'à ce
        qu'un `REPLAY` / `BACK_TO_MENU` la libère.
        """
        borne = await self._borne_store.get_or_create(borne_id)
        if borne.nav is not BorneNavState.IN_GAME:
            return
        borne.nav = BorneNavState.GAME_OVER
        await self._borne_store.update(borne)
        await self._broadcast_nav(borne)

    # --- helpers ---------------------------------------------------------------

    async def _broadcast_nav(self, borne: Borne) -> None:
        await self._broadcaster.broadcast_to_borne(
            borne.borne_id,
            {
                "type": "nav:state",
                "nav": borne.nav.value,
                "sessionId": borne.active_session_id,
            },
        )

    @staticmethod
    def _extract_pseudo(payload: dict | None) -> str | None:
        if not isinstance(payload, dict):
            return None
        pseudo = payload.get("pseudo")
        if isinstance(pseudo, str) and pseudo:
            return pseudo
        players = payload.get("players")
        if isinstance(players, list) and players and isinstance(players[0], str):
            return players[0]
        return None

    @staticmethod
    def _extract_mode(payload: dict | None) -> GameMode:
        raw = payload.get("mode") if isinstance(payload, dict) else None
        try:
            return GameMode(raw)
        except (ValueError, TypeError):
            return GameMode.SOLO
