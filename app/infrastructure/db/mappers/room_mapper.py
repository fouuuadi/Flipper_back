from app.domain.game import GameMode
from app.domain.room import Room, RoomStatus


def row_to_room(row: dict | None) -> Room | None:
    if row is None:
        return None
    return Room(
        id=row["id"],
        code=row["code"],
        mode=GameMode(row["mode"]),
        status=RoomStatus(row["status"]),
        created_at=row["created_at"],
    )
