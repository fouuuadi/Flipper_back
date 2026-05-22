import asyncio
import json
import os
import uuid

import aiomqtt
import pytest
import pytest_asyncio

from app.domain.ports.mqtt_gateway import MqttEvent
from app.infrastructure.mqtt.aio_mqtt_gateway import AioMqttGateway

MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))


class _RecordingHandler:
    def __init__(self) -> None:
        self.events: list[MqttEvent] = []
        self.received = asyncio.Event()

    async def __call__(self, event: MqttEvent) -> None:
        self.events.append(event)
        self.received.set()


@pytest_asyncio.fixture
async def topic_prefix() -> str:
    return f"pytest_{uuid.uuid4().hex}"


async def _publish(topic: str, payload: bytes | str) -> None:
    async with aiomqtt.Client(hostname=MQTT_HOST, port=MQTT_PORT) as pub:
        await pub.publish(topic, payload=payload)


@pytest.mark.asyncio
async def test_gateway_dispatches_json_payload(topic_prefix):
    handler = _RecordingHandler()
    gw = AioMqttGateway(MQTT_HOST, MQTT_PORT, f"{topic_prefix}/#", handler)
    await gw.start()
    try:
        await _publish(
            f"{topic_prefix}/bumper/hit",
            json.dumps({"bumperId": 1, "points": 100, "sessionId": "abc"}),
        )
        await asyncio.wait_for(handler.received.wait(), timeout=3.0)

        assert len(handler.events) == 1
        event = handler.events[0]
        assert event.topic == f"{topic_prefix}/bumper/hit"
        assert event.payload == {"bumperId": 1, "points": 100, "sessionId": "abc"}
    finally:
        await gw.stop()


@pytest.mark.asyncio
async def test_gateway_filters_topics_outside_subscription(topic_prefix):
    handler = _RecordingHandler()
    gw = AioMqttGateway(MQTT_HOST, MQTT_PORT, f"{topic_prefix}/#", handler)
    await gw.start()
    try:
        await _publish(f"other_{uuid.uuid4().hex}/noise", json.dumps({"x": 1}))
        await _publish(f"{topic_prefix}/match", json.dumps({"x": 2}))
        await asyncio.wait_for(handler.received.wait(), timeout=3.0)

        # The off-filter message must not show up.
        assert all(e.topic.startswith(topic_prefix + "/") for e in handler.events)
        assert any(e.payload == {"x": 2} for e in handler.events)
    finally:
        await gw.stop()


@pytest.mark.asyncio
async def test_gateway_drops_non_json_payloads(topic_prefix):
    handler = _RecordingHandler()
    gw = AioMqttGateway(MQTT_HOST, MQTT_PORT, f"{topic_prefix}/#", handler)
    await gw.start()
    try:
        await _publish(f"{topic_prefix}/garbage", b"not-json")
        await _publish(f"{topic_prefix}/ok", json.dumps({"ok": True}))
        await asyncio.wait_for(handler.received.wait(), timeout=3.0)

        # The garbage message is silently dropped; only the valid one reaches the handler.
        topics = [e.topic for e in handler.events]
        assert f"{topic_prefix}/ok" in topics
        assert f"{topic_prefix}/garbage" not in topics
    finally:
        await gw.stop()


@pytest.mark.asyncio
async def test_gateway_drops_non_object_payloads(topic_prefix):
    handler = _RecordingHandler()
    gw = AioMqttGateway(MQTT_HOST, MQTT_PORT, f"{topic_prefix}/#", handler)
    await gw.start()
    try:
        await _publish(f"{topic_prefix}/array", json.dumps([1, 2, 3]))
        await _publish(f"{topic_prefix}/obj", json.dumps({"ok": True}))
        await asyncio.wait_for(handler.received.wait(), timeout=3.0)

        topics = [e.topic for e in handler.events]
        assert f"{topic_prefix}/obj" in topics
        assert f"{topic_prefix}/array" not in topics
    finally:
        await gw.stop()


@pytest.mark.asyncio
async def test_gateway_raises_when_broker_unreachable():
    handler = _RecordingHandler()
    # Pick an unused high port to force a connection failure quickly.
    gw = AioMqttGateway("127.0.0.1", 1, "test/#", handler)
    with pytest.raises(RuntimeError):
        await gw.start()


@pytest.mark.asyncio
async def test_gateway_double_start_raises(topic_prefix):
    handler = _RecordingHandler()
    gw = AioMqttGateway(MQTT_HOST, MQTT_PORT, f"{topic_prefix}/#", handler)
    await gw.start()
    try:
        with pytest.raises(RuntimeError):
            await gw.start()
    finally:
        await gw.stop()


@pytest.mark.asyncio
async def test_gateway_stop_is_idempotent():
    handler = _RecordingHandler()
    gw = AioMqttGateway(MQTT_HOST, MQTT_PORT, "test/#", handler)
    # stop without start must not raise
    await gw.stop()
