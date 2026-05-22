from abc import ABC, abstractmethod


class SessionEventBroadcaster(ABC):
    """Send a JSON message to every client subscribed to a given session."""

    @abstractmethod
    async def broadcast_to_session(self, session_id: str, message: dict) -> None: ...
