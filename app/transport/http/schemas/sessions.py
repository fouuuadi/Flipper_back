from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.game import GameMode


class CreateSessionRequest(BaseModel):
    pseudo: str = Field(min_length=1, max_length=3)
    mode: GameMode = GameMode.SOLO
    room_code: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: str
    pseudo: str
    status: str
    mode: str
    room_code: str | None = None


class ReadyUpResponse(BaseModel):
    session_id: str
    status: str
