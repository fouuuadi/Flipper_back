from __future__ import annotations

from pydantic import BaseModel, Field


class FinishSessionRequest(BaseModel):
    session_id: str = Field(alias="sessionId")

    model_config = {"populate_by_name": True}


class FinishSessionResponse(BaseModel):
    ok: bool = True
    final_score: int = Field(serialization_alias="finalScore")
    player_id: int = Field(serialization_alias="playerId")
    game_id: int = Field(serialization_alias="gameId")
    event_count: int = Field(serialization_alias="eventCount")

    model_config = {"populate_by_name": True}
