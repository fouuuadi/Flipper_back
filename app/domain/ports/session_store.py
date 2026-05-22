from abc import ABC, abstractmethod

from app.domain.session import Session


class SessionStore(ABC):
    @abstractmethod
    async def create(self, session: Session) -> None:
        ...

    @abstractmethod
    async def get(self, session_id: str) -> Session | None:
        ...

    @abstractmethod
    async def update(self, session: Session) -> None:
        ...

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        ...
