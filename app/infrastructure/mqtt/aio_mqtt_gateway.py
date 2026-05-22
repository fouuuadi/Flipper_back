from __future__ import annotations

import asyncio
import json
import logging

import aiomqtt

from app.domain.ports.mqtt_gateway import MqttEvent, MqttEventHandler, MqttGateway

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT_SECONDS = 10.0


class AioMqttGateway(MqttGateway):
    """`aiomqtt`-backed implementation of `MqttGateway`.

    Holds the aiomqtt context manager for the lifetime of a background consumer
    task; `start()` only returns once the SUBSCRIBE has been ack'd, so callers
    can publish immediately after.
    """

    def __init__(
        self,
        host: str,
        port: int,
        topic_filter: str,
        handler: MqttEventHandler,
    ):
        self._host = host
        self._port = port
        self._topic_filter = topic_filter
        self._handler = handler
        self._task: asyncio.Task | None = None
        self._ready = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("MQTT gateway already started")
        self._task = asyncio.create_task(self._run(), name="mqtt-consumer")
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=_CONNECT_TIMEOUT_SECONDS)
        except asyncio.TimeoutError as exc:
            self._task.cancel()
            raise RuntimeError(
                f"MQTT broker {self._host}:{self._port} unreachable"
            ) from exc
        if self._task.done():
            # consumer crashed before signaling ready — surface a clean error
            exc = self._task.exception()
            if exc is not None:
                raise RuntimeError(
                    f"MQTT broker {self._host}:{self._port} unreachable: {exc}"
                ) from exc

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None
        self._ready.clear()

    async def _run(self) -> None:
        try:
            async with aiomqtt.Client(hostname=self._host, port=self._port) as client:
                await client.subscribe(self._topic_filter)
                logger.info(
                    "Subscribed to MQTT topic filter %s on %s:%s",
                    self._topic_filter,
                    self._host,
                    self._port,
                )
                self._ready.set()
                async for message in client.messages:
                    await self._dispatch(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("MQTT consumer crashed")
            # unblock any waiter on start()
            self._ready.set()
            raise

    async def _dispatch(self, message: aiomqtt.Message) -> None:
        topic = str(message.topic)
        try:
            payload = json.loads(message.payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Discarding MQTT message on %s: invalid JSON", topic)
            return
        if not isinstance(payload, dict):
            logger.warning("Discarding MQTT message on %s: payload is not a JSON object", topic)
            return
        event = MqttEvent(topic=topic, payload=payload)
        try:
            await self._handler(event)
        except Exception:
            logger.exception("MQTT handler failed for topic %s", topic)


async def log_mqtt_event(event: MqttEvent) -> None:
    """Default handler used until the use-case bridge lands (#87)."""
    logger.info("MQTT event: topic=%s payload=%s", event.topic, event.payload)
