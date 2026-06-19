import asyncio

import pytest

from app.domain.ports.mqtt_gateway import MqttEvent
from app.usecase.handle_borne_input_usecase import HandleBorneInputUseCase

BORNE_ID = "borne-test"
BUTTON_TOPIC = "pinball/esp32-test/input/button"
PLUNGER_TOPIC = "pinball/esp32-test/input/plunger"


class RecordingBroadcaster:
    def __init__(self):
        self.messages: list[dict] = []

    async def broadcast_to_borne(self, borne_id: str, message: dict) -> None:
        self.messages.append(message)

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        self.messages.append(message)


def _make(delay: float = 0.0):
    broadcaster = RecordingBroadcaster()
    usecase = HandleBorneInputUseCase(BORNE_ID, broadcaster, tap_release_delay_s=delay)
    return usecase, broadcaster


def _button(button_id: str, state: int = 0) -> MqttEvent:
    return MqttEvent(topic=BUTTON_TOPIC, payload={"id": button_id, "state": state, "ts": 1})


# --- navigation : un message = une action -----------------------------------


@pytest.mark.parametrize(
    "button_id,expected",
    [("top", "confirm"), ("bottom", "back"), ("L2", "left"), ("R2", "right"), ("middle", "help")],
)
@pytest.mark.asyncio
async def test_nav_relayed_once_per_press(button_id, expected):
    usecase, broadcaster = _make()

    await usecase.handle(_button(button_id))

    assert broadcaster.messages == [{"type": "control:nav", "button": expected}]


# --- flippers : coup bref (press immédiat, release différé) ------------------


@pytest.mark.asyncio
async def test_left_flipper_taps_press_then_release():
    usecase, broadcaster = _make(delay=0)

    await usecase.handle(_button("L1"))
    assert broadcaster.messages == [
        {"type": "control:flipper", "side": "left", "action": "press"}
    ]

    await asyncio.sleep(0.01)  # laisse la tâche de release s'exécuter
    assert broadcaster.messages == [
        {"type": "control:flipper", "side": "left", "action": "press"},
        {"type": "control:flipper", "side": "left", "action": "release"},
    ]


@pytest.mark.asyncio
async def test_right_flipper_side():
    usecase, broadcaster = _make(delay=0)

    await usecase.handle(_button("R1"))
    await asyncio.sleep(0.01)

    assert broadcaster.messages == [
        {"type": "control:flipper", "side": "right", "action": "press"},
        {"type": "control:flipper", "side": "right", "action": "release"},
    ]


# --- plunger : coup bref ----------------------------------------------------


@pytest.mark.asyncio
async def test_plunger_taps_charge_then_release():
    usecase, broadcaster = _make(delay=0)

    await usecase.handle(MqttEvent(topic=PLUNGER_TOPIC, payload={"state": 1, "ts": 1}))
    assert broadcaster.messages == [{"type": "control:plunger", "action": "charge"}]

    await asyncio.sleep(0.01)
    assert broadcaster.messages == [
        {"type": "control:plunger", "action": "charge"},
        {"type": "control:plunger", "action": "release"},
    ]


# --- robustesse -------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_button_is_ignored():
    usecase, broadcaster = _make()

    await usecase.handle(_button("does-not-exist"))
    await asyncio.sleep(0.01)

    assert broadcaster.messages == []


@pytest.mark.asyncio
async def test_malformed_payload_is_ignored():
    usecase, broadcaster = _make()

    await usecase.handle(MqttEvent(topic=BUTTON_TOPIC, payload={"state": 0}))

    assert broadcaster.messages == []
