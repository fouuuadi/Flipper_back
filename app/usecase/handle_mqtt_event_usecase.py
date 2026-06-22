from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

from app.domain.ports.event_buffer import EventBuffer
from app.domain.ports.mqtt_gateway import MqttEvent
from app.domain.ports.session_event_broadcaster import SessionEventBroadcaster
from app.domain.ports.session_store import SessionStore
from app.domain.session import Session, SessionStatus

logger = logging.getLogger(__name__)

TOPIC_BUMPER_HIT = "flipper/bumper/hit"
TOPIC_BONUS = "flipper/bonus"
TOPIC_BALL_LOST = "flipper/ball/lost"
TOPIC_GAME_OVER = "flipper/game/over"


class HandleMqttEventUseCase:
    """Pont events MQTT → mise à jour de la session Redis → broadcast WS.

    Chaque event porte un `sessionId` dans son payload ; on charge la session
    Redis correspondante, on la mute selon le topic, on persiste, on archive
    l'event dans le buffer par session (consommé au moment du flush par
    `FinishAndPersistUseCase`), et on notifie le client WS connecté.
    """

    def __init__(
        self,
        session_store: SessionStore,
        broadcaster: SessionEventBroadcaster,
        event_buffer: EventBuffer,
        on_game_over: Callable[[str], Awaitable[None]] | None = None,
    ):
        self._session_store = session_store
        self._broadcaster = broadcaster
        self._event_buffer = event_buffer
        # Déclenché (avec session_id) juste après le broadcast d'un game over
        # naturel. Le câblage réel l'utilise pour auto-persister la partie et
        # basculer la borne en `game_over` ; injecté en callback pour que ce use
        # case reste ignorant de la persistance et des bornes.
        self._on_game_over = on_game_over

    async def execute(self, event: MqttEvent) -> None:
        session_id = event.payload.get("sessionId")
        if not isinstance(session_id, str) or not session_id:
            logger.warning("MQTT event on %s missing sessionId", event.topic)
            return

        session = await self._session_store.get(session_id)
        if session is None:
            logger.warning(
                "MQTT event on %s for unknown session %s",
                event.topic,
                session_id,
            )
            return

        # On conditionne les events score/ball au fait que la session soit
        # activement en PLAYING. Pendant READY (countdown), PAUSED (pause UI)
        # ou OVER, le hardware peut continuer d'émettre des events MQTT mais
        # ils ne doivent pas polluer le score.
        if session.status is not SessionStatus.PLAYING:
            logger.debug(
                "MQTT event on %s dropped: session %s is %s (not PLAYING)",
                event.topic,
                session_id,
                session.status.value,
            )
            return

        ws_message = self._apply(event, session)
        if ws_message is None:
            return  # topic inconnu / ignoré — session laissée intacte

        await self._session_store.update(session)
        await self._event_buffer.push(
            session_id,
            {
                "topic": event.topic,
                "payload": event.payload,
                "occured_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        await self._broadcaster.broadcast_to_session(session_id, ws_message)

        # `flipper/game/over` déclenche deux messages distincts : `game:over`
        # (notification du score final, déjà construit par _apply) et
        # `match:state: over` (transition du cycle de vie de la session qui
        # amène la state machine du front vers gameOver). Les clients front
        # peuvent s'abonner à celui dont ils ont besoin.
        if event.topic == TOPIC_GAME_OVER:
            await self._broadcaster.broadcast_to_session(
                session_id,
                {
                    "type": "match:state",
                    "status": session.status.value,
                    "sessionId": session_id,
                },
            )
            if self._on_game_over is not None:
                await self._on_game_over(session_id)

    @staticmethod
    def _apply(event: MqttEvent, session: Session) -> dict | None:
        topic = event.topic
        payload = event.payload

        if topic == TOPIC_BUMPER_HIT:
            points = int(payload.get("points", 0))
            session.score += points
            session.combo += 1
            return {
                "type": "score:update",
                "score": session.score,
                "combo": session.combo,
                "bumperId": payload.get("bumperId"),
            }

        if topic == TOPIC_BONUS:
            points = int(payload.get("points", 0))
            session.score += points
            return {
                "type": "score:update",
                "score": session.score,
                "combo": session.combo,
                "bonusType": payload.get("type"),
            }

        if topic == TOPIC_BALL_LOST:
            session.lives = max(0, session.lives - 1)
            session.combo = 0
            return {
                "type": "ball:lost",
                "livesRemaining": session.lives,
            }

        if topic == TOPIC_GAME_OVER:
            session.status = SessionStatus.OVER
            return {
                "type": "game:over",
                "finalScore": session.score,
            }

        logger.debug("Ignoring MQTT topic %s", topic)
        return None
