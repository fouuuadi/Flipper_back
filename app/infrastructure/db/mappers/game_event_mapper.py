from app.domain.game_event import GameEvent, GameEventType


def row_to_game_event(row: dict | None) -> GameEvent | None:
    if row is None:
        return None
    return GameEvent(
        id=row["id"],
        game_id=row["game_id"],
        type=GameEventType(row["type"]),
        points=row["points"],
        occured_at=row["occured_at"],
    )
