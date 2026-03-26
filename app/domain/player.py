from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Player(BaseModel):
    id: int | None = None
    pseudo: str
    created_at: datetime = datetime.now()
