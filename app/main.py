import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from app.infrastructure.db.mysql import connect, disconnect
from app.transport.http.health import router as health_router
from app.transport.http.root import router as root_router
from app.transport.ws.handler import router as ws_router

load_dotenv()

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    yield
    await disconnect()


app = FastAPI(title="Flipper Backend", lifespan=lifespan)

# Routes HTTP
app.include_router(root_router)
app.include_router(health_router)

# Routes WebSocket
app.include_router(ws_router)

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("APP_PORT", "8080"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
