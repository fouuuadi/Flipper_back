from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# Same input contract as POST /sessions: 3 alphanum + optional "#" + 5 alphanum.
PLAYER_PSEUDO_INPUT_PATTERN = r"^[A-Za-z0-9]{3}(#[A-Za-z0-9]{5})?$"


class CreatePlayerRequest(BaseModel):
    pseudo: str = Field(pattern=PLAYER_PSEUDO_INPUT_PATTERN)


class PlayerResponse(BaseModel):
    id: int
    pseudo: str
    created_at: datetime
