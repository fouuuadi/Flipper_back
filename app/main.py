from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import di
from app.bootstrap import build_runtime
from app.config import get_settings
from app.infrastructure.db.postgres import connect, disconnect
from app.infrastructure.redis import client as redis_client
from app.logging_config import configure_logging
from app.transport.http.error_handler import register_error_handlers
from app.transport.http.games import router as games_router
from app.transport.http.health import router as health_router
from app.transport.http.leaderboard import router as leaderboard_router
from app.transport.http.logging_middleware import http_logging_middleware
from app.transport.http.players import router as players_router
from app.transport.http.root import router as root_router
from app.transport.http.rooms import router as rooms_router
from app.transport.http.scores import router as scores_router
from app.transport.http.sessions import router as sessions_router
from app.transport.ws.handler import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ouvre les connexions d'infra au démarrage, câble le runtime, ferme à l'arrêt."""
    settings = get_settings()
    configure_logging(settings.log_level)

    di.set_db_pool(await connect(settings))
    redis = await redis_client.connect(settings.redis_url)
    di.set_redis_client(redis)

    # Tout l'assemblage des use cases + le démarrage MQTT vivent dans bootstrap.py.
    runtime = await build_runtime(di.container, settings)

    yield

    await runtime.mqtt_gateway.stop()
    await redis_client.disconnect(redis)
    await disconnect()


app = FastAPI(title="Flipper Backend", lifespan=lifespan)

app.middleware("http")(http_logging_middleware)
register_error_handlers(app)

# Routes HTTP
app.include_router(root_router)
app.include_router(health_router)
app.include_router(games_router)
app.include_router(rooms_router)
app.include_router(sessions_router)
app.include_router(scores_router)
app.include_router(players_router)
app.include_router(leaderboard_router)

# Routes WebSocket
app.include_router(ws_router)


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.app_port, reload=True)
