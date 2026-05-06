"""
injection de dépendances pour les repositories
"""

import aiomysql
from app.infrastructure.db.player_repository import PlayerRepository
from app.infrastructure.db.room_repository import RoomRepository
from app.infrastructure.db.game_repository import GameRepository
from app.infrastructure.db.game_event_repository import GameEventRepository

_db_pool: aiomysql.Pool | None = None


def set_db_pool(pool: aiomysql.Pool):
    global _db_pool
    _db_pool = pool


def get_player_repo() -> PlayerRepository:
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return PlayerRepository(_db_pool)


def get_room_repo() -> RoomRepository:
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return RoomRepository(_db_pool)


def get_game_repo() -> GameRepository:
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return GameRepository(_db_pool)


def get_event_repo() -> GameEventRepository:
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return GameEventRepository(_db_pool)
