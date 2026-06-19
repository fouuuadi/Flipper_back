from __future__ import annotations

import asyncio
import logging

from app.domain.ports.borne_event_broadcaster import BorneEventBroadcaster
from app.domain.ports.mqtt_gateway import MqttEvent

logger = logging.getLogger(__name__)


# Mapping bouton physique (id publié par l'ESP32) → sens dans le jeu.
_BUTTON_MAP: dict[str, tuple[str, str]] = {
    "L1": ("flipper", "left"),
    "R1": ("flipper", "right"),
    "L2": ("nav", "left"),
    "R2": ("nav", "right"),
    "top": ("nav", "confirm"),
    "bottom": ("nav", "back"),
    "middle": ("nav", "help"),
}

# Durée du « coup » de flipper / lanceur (cf. note ci-dessous).
_TAP_RELEASE_DELAY_S = 0.12


class HandleBorneInputUseCase:
    """Relaie les entrées physiques de la borne (MQTT) aux 3 écrans.

    ⚠️ Adapté au firmware actuel de l'ESP32 (partagé) : celui-ci a un bug
    press/release et n'émet **qu'un seul message par appui**, sans distinguer
    pressé de relâché (boutons toujours `state:0`, plunger toujours `state:1`).
    On traite donc **chaque message comme un appui ponctuel** :

    - nav → un `control:nav` par appui ;
    - flipper / plunger → un « coup » bref (`press`/`charge` immédiat, puis
      `release` après un court délai), faute de pouvoir maintenir.

    Quand un firmware émettant un vrai press/release sera flashé, revenir à un
    relais direct de l'état (cf. historique git).
    """

    def __init__(
        self,
        borne_id: str,
        broadcaster: BorneEventBroadcaster,
        tap_release_delay_s: float = _TAP_RELEASE_DELAY_S,
    ):
        self._borne_id = borne_id
        self._broadcaster = broadcaster
        self._tap_release_delay_s = tap_release_delay_s

    async def handle(self, event: MqttEvent) -> None:
        if event.topic.endswith("/plunger"):
            await self._tap({"type": "control:plunger", "action": "charge"}, {"action": "release"})
            logger.info("[borne-input] plunger → tap")
        elif event.topic.endswith("/button"):
            await self._handle_button(event.payload)
        else:
            logger.debug("borne input on unhandled topic %s", event.topic)

    async def _handle_button(self, payload: dict) -> None:
        button_id = payload.get("id")
        if not isinstance(button_id, str):
            logger.warning("malformed borne button event: %r", payload)
            return

        mapping = _BUTTON_MAP.get(button_id)
        logger.info("[borne-input] button id=%s → %s", button_id, mapping or "unmapped")
        if mapping is None:
            return

        kind, value = mapping
        if kind == "nav":
            await self._broadcast({"type": "control:nav", "button": value})
        else:  # flipper
            await self._tap(
                {"type": "control:flipper", "side": value, "action": "press"},
                {"action": "release"},
            )

    async def _tap(self, press: dict, release_patch: dict) -> None:
        """Diffuse l'appui, puis le relâché après un court délai (coup bref)."""
        await self._broadcast(press)
        release = {**press, **release_patch}

        async def _release_later() -> None:
            await asyncio.sleep(self._tap_release_delay_s)
            await self._broadcast(release)

        asyncio.create_task(_release_later())

    async def _broadcast(self, message: dict) -> None:
        await self._broadcaster.broadcast_to_borne(self._borne_id, message)
