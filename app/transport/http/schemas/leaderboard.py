from __future__ import annotations

from pydantic import BaseModel


class LeaderboardEntryDTO(BaseModel):
    rank: int
    player_id: int
    pseudo: str
    score: int


class LeaderboardResponse(BaseModel):
    mode: str | None
    limit: int
    entries: list[LeaderboardEntryDTO]
