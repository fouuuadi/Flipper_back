from app.domain.game import Game, GameMode, GameStatus


def row_to_game(row: dict | None) -> Game | None:
    if row is None:
        return None
    return Game(
        id=row["id"],
        match_id=row["match_id"],
        player_id=row["player_id"],
        room_id=row["room_id"],
        mode=GameMode(row["mode"]),
        score=row["score"],
        status=GameStatus(row["status"]),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )
