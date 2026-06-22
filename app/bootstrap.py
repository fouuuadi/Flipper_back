"""Assemblage runtime de l'application : câble les use cases et le routage MQTT.

Séparé de `main.py` pour que celui-ci ne fasse plus QUE créer l'app FastAPI et
monter les routes. Tout le « composition wiring » (qui dépend de quoi, comment les
events MQTT sont aiguillés) vit ici, à un seul endroit.
"""

from dataclasses import dataclass

from app.config import Settings
from app.di import Container
from app.domain.ports.mqtt_gateway import MqttEvent
from app.infrastructure.mqtt.aio_mqtt_gateway import AioMqttGateway
from app.infrastructure.ws.composite_broadcaster import CompositeBroadcaster
from app.usecase.apply_borne_intent_usecase import ApplyBorneIntentUseCase
from app.usecase.finish_and_persist_usecase import FinishAndPersistUseCase
from app.usecase.finish_borne_game_usecase import FinishBorneGameUseCase
from app.usecase.handle_borne_input_usecase import HandleBorneInputUseCase
from app.usecase.handle_mqtt_event_usecase import HandleMqttEventUseCase


@dataclass
class Runtime:
    """Ressources démarrées au boot que le lifespan devra arrêter à la fermeture."""

    mqtt_gateway: AioMqttGateway


async def build_runtime(container: Container, settings: Settings) -> Runtime:
    """Câble les use cases borne/match et démarre le gateway MQTT.

    Suppose que le pool Postgres et le client Redis sont déjà posés sur le
    `container` (fait par le lifespan avant cet appel).
    """
    # Les events MQTT sont diffusés à la fois au hub de session (front legacy en
    # `?session_id`) et au bus borne (les 3 écrans en `?borne_id`).
    mqtt_broadcaster = CompositeBroadcaster(
        container.session_hub_manager(),
        container.borne_hub_manager(),
    )

    # Game over naturel → persistance auto + bascule borne `game_over`, mais
    # seulement pour la session active de la borne (le legacy garde `POST /scores`).
    apply_intent = ApplyBorneIntentUseCase(
        container.borne_store(), container.borne_hub_manager(), container.session_store()
    )
    finish_borne_game = FinishBorneGameUseCase(
        borne_store=container.borne_store(),
        borne_id=container.borne_id(),
        apply_intent=apply_intent,
        finish_and_persist=FinishAndPersistUseCase(
            session_store=container.session_store(),
            event_buffer=container.event_buffer(),
            game_repository=container.game_repo(),
            player_repository=container.player_repo(),
        ),
    )
    handle_event_usecase = HandleMqttEventUseCase(
        session_store=container.session_store(),
        broadcaster=mqtt_broadcaster,
        event_buffer=container.event_buffer(),
        on_game_over=finish_borne_game.execute,
    )

    # Entrées physiques de la borne (boutons / plunger ESP32) → relayées aux 3
    # écrans (flippers/plunger + nav). Le front oriente la nav selon l'écran.
    handle_borne_input = HandleBorneInputUseCase(
        borne_id=container.borne_id(),
        broadcaster=container.borne_hub_manager(),
    )

    async def mqtt_handler(event: MqttEvent) -> None:
        # Entrées borne et capteurs de jeu partagent le broker mais ont des
        # préfixes distincts : on aiguille sur le segment `/input/`.
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
    container.set_mqtt_gateway(mqtt_gateway)
    return Runtime(mqtt_gateway=mqtt_gateway)
