from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.game import GameMode

# Accepte 3 caractères alphanum, éventuellement suivis de "#" + exactement
# 5 alphanum. La normalisation (uppercase + HETIC par défaut) se fait dans le
# use case.
PSEUDO_INPUT_PATTERN = r"^[A-Za-z0-9]{3}(#[A-Za-z0-9]{5})?$"


class CreateSessionRequest(BaseModel):
    pseudo: str = Field(pattern=PSEUDO_INPUT_PATTERN)
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
