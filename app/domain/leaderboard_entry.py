from __future__ import annotations

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    """Une ligne du leaderboard.

    Ce n'est pas une table en base — construite en agrégeant `games` (meilleur
    score par joueur) et en joignant `players` pour le pseudo. `rank` est
    calculé par le use case à partir de la liste ordonnée renvoyée par le
    repository (commence à 1).
    """

    rank: int
    player_id: int
    pseudo: str
    score: int
