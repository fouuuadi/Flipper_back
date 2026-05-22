import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.infrastructure.db.mysql import connect, disconnect
from app.infrastructure.redis import client as redis_client
from app import di
from app.transport.http.error_handler import register_error_handlers
from app.transport.http.health import router as health_router
from app.transport.http.root import router as root_router
from app.transport.http.games import router as games_router
from app.transport.http.rooms import router as rooms_router
from app.transport.http.sessions import router as sessions_router
from app.transport.ws.handler import router as ws_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db_pool = await connect(settings)
    di.set_db_pool(db_pool)
    redis = await redis_client.connect(settings.redis_url)
    di.set_redis_client(redis)
    yield
    await redis_client.disconnect(redis)
    await disconnect()

app = FastAPI(title="Flipper Backend", lifespan=lifespan)

register_error_handlers(app)

# Routes HTTP
app.include_router(root_router)
app.include_router(health_router)
app.include_router(games_router)
app.include_router(rooms_router)
app.include_router(sessions_router)

# Routes WebSocket
app.include_router(ws_router)

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.app_port, reload=True)
