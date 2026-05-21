from pydantic import BaseModel

from app.domain.game import GameMode


class StartGameRequest(BaseModel):
    pseudo: str
    mode: GameMode
    room_code: str | None = None


class StartGameResponse(BaseModel):
    player_id: int
    room_code: str
    game_id: int
    event_id: int
