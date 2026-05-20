from pydantic import BaseModel

from app.domain.game_event import GameEventType


class AddEventRequest(BaseModel):
    type: GameEventType
    points: int = 0


class AddEventResponse(BaseModel):
    game_id: int
    new_score: int
    event_id: int
