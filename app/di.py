"""Composition root : assemble les dépendances de l'application.

C'est le seul endroit où les classes concrètes (`Pg*Repository`, `Redis*Store`…)
rencontrent les ports du domaine. Le reste du code ne dépend que des abstractions.

L'état d'infra (pool Postgres, client Redis, gateway MQTT) est encapsulé dans un
objet `Container` — pas dans des variables de module mutées via `global`. Les
fonctions `set_*` / `get_*` exposées en fin de fichier sont de minces délégations
vers l'instance unique `container` : FastAPI (`Depends(...)`) et le bootstrap ont
besoin de callables stables, c'est la couture qui les leur fournit.
"""

import asyncpg
from redis.asyncio import Redis

from app.config import get_settings
from app.domain.ports.borne_store import BorneStore
from app.domain.ports.event_buffer import EventBuffer
from app.domain.ports.game_event_repository import GameEventRepository
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.mqtt_gateway import MqttGateway
from app.domain.ports.player_repository import PlayerRepository
from app.domain.ports.room_repository import RoomRepository
from app.domain.ports.session_store import SessionStore
from app.domain.ports.unit_of_work import UnitOfWork
from app.infrastructure.db.game_event_repository import PgGameEventRepository
from app.infrastructure.db.game_repository import PgGameRepository
from app.infrastructure.db.player_repository import PgPlayerRepository
from app.infrastructure.db.room_repository import PgRoomRepository
from app.infrastructure.db.unit_of_work import PgUnitOfWork
from app.infrastructure.redis.borne_store import RedisBorneStore
from app.infrastructure.redis.event_buffer import RedisEventBuffer
from app.infrastructure.redis.session_store import RedisSessionStore
from app.infrastructure.ws.borne_hub import borne_hub_manager
from app.infrastructure.ws.room_hub import hub_manager
from app.infrastructure.ws.session_hub import session_hub_manager


class Container:
    """Conteneur d'injection de dépendances.

    Détient les singletons d'infra (posés au démarrage par le lifespan) et fabrique
    les adapters concrets, toujours typés par leurs ports. Les providers de
    repositories recréent un objet léger par appel autour du pool partagé ; les hubs
    WebSocket sont des singletons (ils gardent la liste des clients connectés).
    """

    def __init__(self) -> None:
        self._db_pool: asyncpg.Pool | None = None
        self._redis_client: Redis | None = None
        self._mqtt_gateway: MqttGateway | None = None

    # --- Enregistrement des singletons d'infra (appelé une fois au démarrage) ---

    def set_db_pool(self, pool: asyncpg.Pool) -> None:
        self._db_pool = pool

    def set_redis_client(self, client: Redis) -> None:
        self._redis_client = client

    def set_mqtt_gateway(self, gateway: MqttGateway) -> None:
        self._mqtt_gateway = gateway

    # --- Accès internes avec garde fail-fast ---

    def _require_pool(self) -> asyncpg.Pool:
        if self._db_pool is None:
            raise RuntimeError("Database pool not initialized")
        return self._db_pool

    def _require_redis(self) -> Redis:
        if self._redis_client is None:
            raise RuntimeError("Redis client not initialized")
        return self._redis_client

    # --- Providers : retournent des types de PORTS, jamais les classes concrètes ---

    def player_repo(self) -> PlayerRepository:
        return PgPlayerRepository(self._require_pool())

    def room_repo(self) -> RoomRepository:
        return PgRoomRepository(self._require_pool())

    def game_repo(self) -> GameRepository:
        return PgGameRepository(self._require_pool())

    def event_repo(self) -> GameEventRepository:
        return PgGameEventRepository(self._require_pool())

    def uow(self) -> UnitOfWork:
        """Renvoie une Unit of Work neuve à chaque appel.

        `__aenter__` acquiert sa propre connexion et ouvre sa propre transaction :
        la UoW est éphémère, à utiliser via `async with uow: ...`.
        """
        return PgUnitOfWork(self._require_pool())

    def session_store(self) -> SessionStore:
        return RedisSessionStore(self._require_redis(), get_settings().redis_session_ttl_seconds)

    def event_buffer(self) -> EventBuffer:
        return RedisEventBuffer(self._require_redis(), get_settings().redis_session_ttl_seconds)

    def borne_store(self) -> BorneStore:
        return RedisBorneStore(self._require_redis())

    def mqtt_gateway(self) -> MqttGateway:
        if self._mqtt_gateway is None:
            raise RuntimeError("MQTT gateway not initialized")
        return self._mqtt_gateway

    # --- Singletons WebSocket et config (pas d'état à initialiser) ---

    def borne_hub_manager(self):
        """Singleton BorneHubManager (canal borne permanent, les 3 écrans)."""
        return borne_hub_manager

    def hub_manager(self):
        """Singleton HubManager (broadcast WebSocket par room, legacy)."""
        return hub_manager

    def session_hub_manager(self):
        """Singleton SessionHubManager (broadcast par session_id)."""
        return session_hub_manager

    def borne_id(self) -> str:
        """Identifiant de la borne servie par cette instance (depuis la config)."""
        return get_settings().borne_id


# Instance unique de composition root. Référence stable vers un objet qui gère son
# propre état — et non une variable d'état mutée globalement.
container = Container()


# --- Couture pour FastAPI `Depends(...)` et le bootstrap -----------------------
# Délégations minces vers `container`. On garde des callables au niveau module pour
# que les routes (`Depends(get_game_repo)`) et les tests (`set_db_pool(pool)`)
# restent stables, sans connaître la mécanique interne du conteneur.

def set_db_pool(pool: asyncpg.Pool) -> None:
    container.set_db_pool(pool)


def set_redis_client(client: Redis) -> None:
    container.set_redis_client(client)


def set_mqtt_gateway(gateway: MqttGateway) -> None:
    container.set_mqtt_gateway(gateway)


def get_player_repo() -> PlayerRepository:
    return container.player_repo()


def get_room_repo() -> RoomRepository:
    return container.room_repo()


def get_game_repo() -> GameRepository:
    return container.game_repo()


def get_event_repo() -> GameEventRepository:
    return container.event_repo()


def get_uow() -> UnitOfWork:
    return container.uow()


def get_session_store() -> SessionStore:
    return container.session_store()


def get_event_buffer() -> EventBuffer:
    return container.event_buffer()


def get_borne_store() -> BorneStore:
    return container.borne_store()


def get_mqtt_gateway() -> MqttGateway:
    return container.mqtt_gateway()


def get_borne_hub_manager():
    return container.borne_hub_manager()


def get_hub_manager():
    return container.hub_manager()


def get_session_hub_manager():
    return container.session_hub_manager()


def get_borne_id() -> str:
    return container.borne_id()
