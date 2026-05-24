"""
injection de dépendances pour les repositories
"""

import asyncpg
from redis.asyncio import Redis

from app.config import get_settings
from app.domain.ports.event_buffer import EventBuffer
from app.domain.ports.game_event_repository import GameEventRepository
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.mqtt_gateway import MqttGateway
from app.domain.ports.player_repository import PlayerRepository
from app.domain.ports.room_repository import RoomRepository
from app.domain.ports.session_store import SessionStore
from app.infrastructure.db.game_event_repository import PgGameEventRepository
from app.infrastructure.db.game_repository import PgGameRepository
from app.infrastructure.db.player_repository import PgPlayerRepository
from app.infrastructure.db.room_repository import PgRoomRepository
from app.infrastructure.redis.event_buffer import RedisEventBuffer
from app.infrastructure.redis.session_store import RedisSessionStore
from app.infrastructure.ws.room_hub import hub_manager
from app.infrastructure.ws.session_hub import session_hub_manager

_db_pool: asyncpg.Pool | None = None
_redis_client: Redis | None = None
_mqtt_gateway: MqttGateway | None = None


def set_db_pool(pool: asyncpg.Pool):
    global _db_pool
    _db_pool = pool


def set_redis_client(client: Redis):
    global _redis_client
    _redis_client = client


def set_mqtt_gateway(gateway: MqttGateway):
    global _mqtt_gateway
    _mqtt_gateway = gateway


def get_player_repo() -> PlayerRepository:
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return PgPlayerRepository(_db_pool)


def get_room_repo() -> RoomRepository:
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return PgRoomRepository(_db_pool)


def get_game_repo() -> GameRepository:
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return PgGameRepository(_db_pool)


def get_event_repo() -> GameEventRepository:
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return PgGameEventRepository(_db_pool)


def get_session_store() -> SessionStore:
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized")
    settings = get_settings()
    return RedisSessionStore(_redis_client, settings.redis_session_ttl_seconds)


def get_event_buffer() -> EventBuffer:
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized")
    settings = get_settings()
    return RedisEventBuffer(_redis_client, settings.redis_session_ttl_seconds)


def get_hub_manager():
    """Retourne le singleton HubManager pour WebSocket broadcasting."""
    return hub_manager


def get_session_hub_manager():
    """Retourne le singleton SessionHubManager (broadcast par session_id)."""
    return session_hub_manager


def get_mqtt_gateway() -> MqttGateway:
    if _mqtt_gateway is None:
        raise RuntimeError("MQTT gateway not initialized")
    return _mqtt_gateway
