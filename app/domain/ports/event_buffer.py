from abc import ABC, abstractmethod
from typing import Any


class EventBuffer(ABC):
    """Ephemeral buffer accumulating raw MQTT events for a session.

    Used during the game so that `POST /scores` can batch-insert the full
    event timeline into `game_events`. Cleared when the session is flushed.
    """

    @abstractmethod
    async def push(self, session_id: str, event: dict[str, Any]) -> None: ...

    @abstractmethod
    async def read_all(self, session_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def clear(self, session_id: str) -> None: ...
