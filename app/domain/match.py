from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Match(BaseModel):
    id: int | None = None
    player1_id: int
    player2_id: int
    player1_score: int = 0
    player2_score: int = 0
    winner_id: int | None = None
    played_at: datetime = datetime.now()
