from __future__ import annotations

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    """A single row of the leaderboard.

    Not a DB table — built by aggregating `games` (best score per player) and
    joining `players` for the pseudo. `rank` is computed by the use case from
    the ordered list returned by the repository (1-based).
    """

    rank: int
    player_id: int
    pseudo: str
    score: int
