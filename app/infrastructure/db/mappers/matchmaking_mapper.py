from app.domain.matchmaking import Matchmaking, MatchmakingStatus


def row_to_matchmaking(row: dict | None) -> Matchmaking | None:
    if row is None:
        return None
    return Matchmaking(
        id=row["id"],
        player1_id=row["player1_id"],
        player2_id=row["player2_id"],
        status=MatchmakingStatus(row["status"]),
        mode=row["mode"],
        created_at=row["created_at"],
    )
