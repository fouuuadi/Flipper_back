from __future__ import annotations

import logging

from app.domain.ports.borne_event_broadcaster import BorneEventBroadcaster
from app.domain.ports.mqtt_gateway import MqttEvent

logger = logging.getLogger(__name__)


# Mapping bouton physique (id publié par l'ESP32) → sens dans le jeu.
# Symétrie de la borne : les deux boutons blancs pilotent les flippers, les deux
# noirs la navigation.
#   id | bouton physique | rôle
_BUTTON_MAP: dict[str, tuple[str, str]] = {
    "L1": ("flipper", "left"),   # blanc gauche
    "R2": ("flipper", "right"),  # blanc droit
    "L2": ("nav", "left"),       # noir gauche
    "R1": ("nav", "right"),      # noir droit
    "top": ("nav", "confirm"),
    "bottom": ("nav", "back"),
    "middle": ("nav", "help"),
}


class HandleBorneInputUseCase:
    """Relaie les entrées physiques de la borne (MQTT) aux 3 écrans.

    Le firmware ESP32 émet un vrai press/release : un message ``state:1`` à
    l'appui, ``state:0`` au relâchement (cf. ``Button::onPress``/``onRelease``).
    On relaie donc l'état réel du bouton :

    - nav → un seul ``control:nav`` à l'appui (``state:1``) ; le relâchement
      (``state:0``) est ignoré, sinon chaque appui déclencherait l'action deux
      fois ;
    - flipper / plunger → ``press``/``charge`` à l'appui, ``release`` au
      relâchement, ce qui permet de maintenir un flipper levé tant que le bouton
      reste enfoncé.
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
        if not isinstance(button_id, str):
            logger.warning("malformed borne button event: %r", payload)
            return

        mapping = _BUTTON_MAP.get(button_id)
        state = payload.get("state")
        logger.info(
            "[borne-input] button id=%s state=%s → %s", button_id, state, mapping or "unmapped"
        )
        if mapping is None or state not in (0, 1):
            return

        kind, value = mapping
        if kind == "nav":
            # Une seule action par appui : on relaie le front montant, pas le
            # relâchement.
            if state == 1:
                await self._broadcast({"type": "control:nav", "button": value})
        else:  # flipper : on suit l'état physique du bouton.
            action = "press" if state == 1 else "release"
            await self._broadcast({"type": "control:flipper", "side": value, "action": action})

    async def _handle_plunger(self, payload: dict) -> None:
        state = payload.get("state")
        if state not in (0, 1):
            logger.warning("malformed borne plunger event: %r", payload)
            return
        action = "charge" if state == 1 else "release"
        await self._broadcast({"type": "control:plunger", "action": action})

    async def _broadcast(self, message: dict) -> None:
        await self._broadcaster.broadcast_to_borne(self._borne_id, message)
