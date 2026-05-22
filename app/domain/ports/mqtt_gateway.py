from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class MqttEvent(BaseModel):
    """Raw event received from the MQTT broker.

    The infrastructure layer parses the JSON payload before constructing this
    object — use cases receive a `dict`, not raw bytes.
    """

    topic: str
    payload: dict[str, Any]


@runtime_checkable
class MqttEventHandler(Protocol):
    async def __call__(self, event: MqttEvent) -> None: ...


class MqttGateway(ABC):
    """Bridge to an MQTT broker.

    Concrete implementations open a connection, subscribe to a topic filter,
    and dispatch every incoming message (with a JSON payload) to the handler
    passed at construction time. The consumer loop runs in a background task
    owned by the gateway.
    """

    @abstractmethod
    async def start(self) -> None:
        """Open the broker connection, subscribe, and start the consumer task."""

    @abstractmethod
    async def stop(self) -> None:
        """Cancel the consumer task and disconnect."""
