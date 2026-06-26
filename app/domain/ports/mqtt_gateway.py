from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class MqttEvent(BaseModel):
    """Event brut reçu du broker MQTT.

    La couche infrastructure parse le payload JSON avant de construire cet
    objet — les use cases reçoivent un `dict`, pas des bytes bruts.
    """

    topic: str
    payload: dict[str, Any]


@runtime_checkable
class MqttEventHandler(Protocol):
    async def __call__(self, event: MqttEvent) -> None: ...


class MqttGateway(ABC):
    """Pont vers un broker MQTT.

    Les implémentations concrètes ouvrent une connexion, s'abonnent à un filtre
    de topic, et dispatchent chaque message entrant (au payload JSON) vers le
    handler passé à la construction. La boucle de consommation tourne dans une
    background task détenue par la gateway.
    """

    @abstractmethod
    async def start(self) -> None:
        """Ouvre la connexion au broker, s'abonne, et démarre la consumer task."""

    @abstractmethod
    async def stop(self) -> None:
        """Annule la consumer task et se déconnecte."""
