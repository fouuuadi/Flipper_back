from pydantic import BaseModel, Field


class MatchmakingRequest(BaseModel):
    player_id: int
    mode: str = Field(..., min_length=2)


class MatchmakingResponse(BaseModel):
    status: str
    room_code: str | None = None
    game_ids: list[int] = Field(default_factory=list)
    matchmaking_id: int | None = None
