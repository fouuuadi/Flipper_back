from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.domain.ports.mqtt_gateway import MqttEvent
from app.infrastructure.db.postgres import connect, disconnect
from app.infrastructure.mqtt.aio_mqtt_gateway import AioMqttGateway
from app.infrastructure.redis import client as redis_client
from app.infrastructure.ws.composite_broadcaster import CompositeBroadcaster
from app.logging_config import configure_logging
from app.usecase.apply_borne_intent_usecase import ApplyBorneIntentUseCase
from app.usecase.finish_and_persist_usecase import FinishAndPersistUseCase
from app.usecase.finish_borne_game_usecase import FinishBorneGameUseCase
from app.usecase.handle_borne_input_usecase import HandleBorneInputUseCase
from app.usecase.handle_mqtt_event_usecase import HandleMqttEventUseCase
from app import di
from app.transport.http.error_handler import register_error_handlers
from app.transport.http.health import router as health_router
from app.transport.http.logging_middleware import http_logging_middleware
from app.transport.http.root import router as root_router
from app.transport.http.games import router as games_router
from app.transport.http.leaderboard import router as leaderboard_router
from app.transport.http.players import router as players_router
from app.transport.http.rooms import router as rooms_router
from app.transport.http.scores import router as scores_router
from app.transport.http.sessions import router as sessions_router
from app.transport.ws.handler import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    db_pool = await connect(settings)
    di.set_db_pool(db_pool)
    redis = await redis_client.connect(settings.redis_url)
    di.set_redis_client(redis)

    # MQTT events fan out to both the legacy session hub (front connecté en
    # `?session_id`) and le bus borne (les 3 écrans en `?borne_id`).
    mqtt_broadcaster = CompositeBroadcaster(
        di.get_session_hub_manager(),
        di.get_borne_hub_manager(),
    )
    # Game over naturel → persistance auto + bascule borne `game_over`, mais
    # uniquement pour la session active de la borne (les sessions legacy
    # gardent `POST /scores`).
    apply_intent = ApplyBorneIntentUseCase(
        di.get_borne_store(), di.get_borne_hub_manager(), di.get_session_store()
    )
    finish_borne_game = FinishBorneGameUseCase(
        borne_store=di.get_borne_store(),
        borne_id=di.get_borne_id(),
        apply_intent=apply_intent,
        finish_and_persist=FinishAndPersistUseCase(
            session_store=di.get_session_store(),
            event_buffer=di.get_event_buffer(),
            game_repository=di.get_game_repo(),
            player_repository=di.get_player_repo(),
        ),
    )
    handle_event_usecase = HandleMqttEventUseCase(
        session_store=di.get_session_store(),
        broadcaster=mqtt_broadcaster,
        event_buffer=di.get_event_buffer(),
        on_game_over=finish_borne_game.execute,
    )

    # Entrées physiques de la borne (boutons / plunger ESP32) → flippers
    # relayés aux écrans + navigation appliquée via le bus borne.
    handle_borne_input = HandleBorneInputUseCase(
        borne_id=di.get_borne_id(),
        borne_store=di.get_borne_store(),
        broadcaster=di.get_borne_hub_manager(),
        apply_intent=apply_intent,
    )

    async def mqtt_handler(event: MqttEvent) -> None:
        # Les entrées borne et les capteurs de jeu partagent le broker mais ont
        # des préfixes distincts : on aiguille sur le segment `/input/`.
        if "/input/" in event.topic:
            await handle_borne_input.handle(event)
        else:
            await handle_event_usecase.execute(event)

    mqtt_gateway = AioMqttGateway(
        host=settings.mqtt_broker_host,
        port=settings.mqtt_broker_port,
        topic_filter=[
            settings.mqtt_topic_filter,
            settings.mqtt_borne_input_topic_filter,
        ],
        handler=mqtt_handler,
    )
    await mqtt_gateway.start()
    di.set_mqtt_gateway(mqtt_gateway)
    yield
    await mqtt_gateway.stop()
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
