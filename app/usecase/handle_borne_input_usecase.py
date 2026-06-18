from __future__ import annotations

import logging

from app.domain.ports.borne_event_broadcaster import BorneEventBroadcaster
from app.domain.ports.mqtt_gateway import MqttEvent

logger = logging.getLogger(__name__)


# Mapping bouton physique (id publié par l'ESP32) → sens dans le jeu.
#
# C'est *la* table de correspondance, volontairement côté backend : le firmware
# reste agnostique du jeu (il envoie juste « L1 pressé »), et on peut re-mapper
# sans reflasher l'ESP32. Deux familles, toutes deux **relayées** au front :
#   - "flipper" → le playfield actionne la 3D.
#   - "nav"     → le front oriente selon l'écran courant (curseur de menu,
#                 roulette d'identification…) ; c'est lui qui connaît l'UI.
#
# `under_plunger` reste libre (réservé).
_BUTTON_MAP: dict[str, tuple[str, str]] = {
    "L1": ("flipper", "left"),
    "R1": ("flipper", "right"),
    "L2": ("nav", "left"),
    "R2": ("nav", "right"),
    "top": ("nav", "confirm"),
    "bottom": ("nav", "back"),
    "middle": ("nav", "help"),
}


class HandleBorneInputUseCase:
    """Relaie les entrées physiques de la borne (MQTT) aux 3 écrans.

    - Flippers / plunger → `control:flipper` / `control:plunger` (le playfield
      actionne la 3D ; même rôle que le clavier en dev).
    - Boutons d'interface → `control:nav` (`confirm/back/left/right/help`). Le
      backend ne décide PAS de l'action ici : le front oriente selon l'écran
      courant (seul lui connaît le curseur / la sélection), puis renvoie l'intent
      final (PRESS_A, START_GAME, PLAYERS_VALIDATED…) que le backend applique.

    Le firmware publie sans `sessionId` : la borne est la seule source d'état.
    """

    def __init__(self, borne_id: str, broadcaster: BorneEventBroadcaster):
        self._borne_id = borne_id
        self._broadcaster = broadcaster

    async def handle(self, event: MqttEvent) -> None:
        if event.topic.endswith("/plunger"):
            await self._handle_plunger(event.payload)
        elif event.topic.endswith("/button"):
            await self._handle_button(event.payload)
        else:
            logger.debug("borne input on unhandled topic %s", event.topic)

    async def _handle_button(self, payload: dict) -> None:
        button_id = payload.get("id")
        state = payload.get("state")
        if not isinstance(button_id, str) or state not in (0, 1):
            logger.warning("malformed borne button event: %r", payload)
            return

        mapping = _BUTTON_MAP.get(button_id)
        logger.info(
            "[borne-input] button id=%s state=%s -> %s",
            button_id,
            state,
            mapping if mapping else "unmapped",
        )
        if mapping is None:
            return

        kind, value = mapping
        if kind == "flipper":
            action = "press" if state == 1 else "release"
            await self._broadcaster.broadcast_to_borne(
                self._borne_id,
                {"type": "control:flipper", "side": value, "action": action},
            )
            return

        # Navigation : on n'agit qu'à l'appui (state == 1), pas au relâché.
        if state == 1:
            await self._broadcaster.broadcast_to_borne(
                self._borne_id,
                {"type": "control:nav", "button": value},
            )

    async def _handle_plunger(self, payload: dict) -> None:
        state = payload.get("state")
        if state not in (0, 1):
            logger.warning("malformed borne plunger event: %r", payload)
            return
        action = "charge" if state == 1 else "release"
        logger.info("[borne-input] plunger state=%s -> %s", state, action)
        await self._broadcaster.broadcast_to_borne(
            self._borne_id,
            {"type": "control:plunger", "action": action},
        )
