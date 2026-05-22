from __future__ import annotations

import logging

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
    """Bridge MQTT events → Redis session update → WS broadcast.

    Each event carries a `sessionId` in its payload; we load the matching
    Redis session, mutate it according to the topic, persist, and notify the
    connected WS client.
    """

    def __init__(
        self,
        session_store: SessionStore,
        broadcaster: SessionEventBroadcaster,
    ):
        self._session_store = session_store
        self._broadcaster = broadcaster

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

        ws_message = self._apply(event, session)
        if ws_message is None:
            return  # unknown / ignored topic — session left untouched

        await self._session_store.update(session)
        await self._broadcaster.broadcast_to_session(session_id, ws_message)

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
