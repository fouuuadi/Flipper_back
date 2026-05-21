from app.domain.player import Player


def row_to_player(row: dict | None) -> Player | None:
    if row is None:
        return None
    return Player(
        id=row["id"],
        pseudo=row["pseudo"],
        created_at=row["created_at"],
    )
