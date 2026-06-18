from __future__ import annotations

import logging

from app.domain.borne import BorneNavState
from app.domain.ports.borne_event_broadcaster import BorneEventBroadcaster
from app.domain.ports.borne_store import BorneStore
from app.domain.ports.mqtt_gateway import MqttEvent
from app.usecase.apply_borne_intent_usecase import ApplyBorneIntentUseCase

logger = logging.getLogger(__name__)


# Mapping bouton physique (id publié par l'ESP32) → sens dans le jeu.
#
# C'est *la* table de correspondance, volontairement côté backend : le firmware
# reste agnostique du jeu (il envoie juste « L1 pressé »), et on peut re-mapper
# sans reflasher l'ESP32. Deux familles :
#   - "flipper" → relayé tel quel aux 3 écrans (le playfield actionne la 3D).
#   - "nav"     → action sémantique résolue selon l'état de navigation courant.
#
# `under_plunger` et la navigation directionnelle (`LEFT`/`RIGHT`) sont réservés
# au menu à curseur (lot ultérieur) — voir `_resolve_nav`.
_BUTTON_MAP: dict[str, tuple[str, str]] = {
    "L1": ("flipper", "left"),
    "R1": ("flipper", "right"),
    "L2": ("nav", "LEFT"),
    "R2": ("nav", "RIGHT"),
    "top": ("nav", "CONFIRM"),
    "bottom": ("nav", "BACK"),
    "middle": ("nav", "SECONDARY"),
}


def _resolve_nav(nav: BorneNavState, semantic: str) -> tuple[str, str] | None:
    """Traduit un bouton sémantique en action concrète selon l'état courant.

    Retourne `("intent", action)` (transition de navigation via
    `ApplyBorneIntentUseCase.execute`) ou `("cmd", cmd)` (contrôle de match via
    `handle_match_command`), ou `None` si le bouton n'a pas de sens ici.
    """
    if semantic == "CONFIRM":
        return {
            BorneNavState.SPLASH: ("intent", "PRESS_A"),
            BorneNavState.MENU: ("intent", "START_GAME"),
            BorneNavState.BOUTIQUE: ("intent", "START_GAME"),
            BorneNavState.GAME_OVER: ("intent", "REPLAY"),
        }.get(nav)

    if semantic == "BACK":
        if nav is BorneNavState.IN_GAME:
            # En jeu, le bouton « retour » met la partie en pause.
            return ("cmd", "cmd:pause")
        return {
            BorneNavState.IDENTIFICATION: ("intent", "BACK_TO_MENU"),
            BorneNavState.BOUTIQUE: ("intent", "BACK_TO_MENU"),
            BorneNavState.LEADERBOARD: ("intent", "BACK_TO_MENU"),
            BorneNavState.SETTINGS: ("intent", "BACK_TO_MENU"),
            BorneNavState.GAME_OVER: ("intent", "BACK_TO_MENU"),
        }.get(nav)

    # LEFT / RIGHT (navigation directionnelle) et SECONDARY : nécessitent le
    # menu à curseur, pas encore en place. Ignorés pour l'instant.
    return None


class HandleBorneInputUseCase:
    """Route les entrées physiques de la borne (MQTT) vers le bon canal.

    - Flippers → broadcast `control:flipper` sur le bus borne (le playfield
      actionne le flipper 3D ; même rôle que le clavier en dev).
    - Plunger → broadcast `control:plunger`.
    - Boutons de navigation → action résolue puis appliquée via
      `ApplyBorneIntentUseCase` (réutilise toute la logique existante).

    Le firmware publie sans `sessionId` : c'est le backend qui sait, via la
    borne, quelle session/phase est active.
    """

    def __init__(
        self,
        borne_id: str,
        borne_store: BorneStore,
        broadcaster: BorneEventBroadcaster,
        apply_intent: ApplyBorneIntentUseCase,
    ):
        self._borne_id = borne_id
        self._borne_store = borne_store
        self._broadcaster = broadcaster
        self._apply_intent = apply_intent

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
            logger.info("[borne-input] flipper %s %s", value, action)
            await self._broadcaster.broadcast_to_borne(
                self._borne_id,
                {"type": "control:flipper", "side": value, "action": action},
            )
            return

        # Navigation : on n'agit qu'à l'appui (state == 1), pas au relâché.
        if state == 1:
            await self._apply_nav(value)

    async def _apply_nav(self, semantic: str) -> None:
        borne = await self._borne_store.get_or_create(self._borne_id)
        resolved = _resolve_nav(borne.nav, semantic)
        logger.info(
            "[borne-input] nav %s in nav=%s -> %s",
            semantic,
            borne.nav.value,
            resolved if resolved else "no-op",
        )
        if resolved is None:
            return
        kind, action = resolved
        if kind == "intent":
            await self._apply_intent.execute(self._borne_id, action)
        else:  # "cmd"
            await self._apply_intent.handle_match_command(self._borne_id, action)

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
