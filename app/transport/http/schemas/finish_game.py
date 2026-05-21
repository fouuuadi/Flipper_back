from datetime import datetime

from pydantic import BaseModel


class FinishGameResponse(BaseModel):
    game_id: int
    status: str
    finished_at: datetime
    event_id: int
