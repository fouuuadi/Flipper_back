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


def _make():
    broadcaster = RecordingBroadcaster()
    usecase = HandleBorneInputUseCase(BORNE_ID, broadcaster)
    return usecase, broadcaster


def _button(button_id: str, state: int) -> MqttEvent:
    return MqttEvent(topic=BUTTON_TOPIC, payload={"id": button_id, "state": state, "ts": 1})


# --- flippers ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_left_flipper_press_and_release_are_relayed():
    usecase, broadcaster = _make()

    await usecase.handle(_button("L1", 1))
    await usecase.handle(_button("L1", 0))

    assert broadcaster.messages == [
        {"type": "control:flipper", "side": "left", "action": "press"},
        {"type": "control:flipper", "side": "left", "action": "release"},
    ]


@pytest.mark.asyncio
async def test_right_flipper_maps_to_right_side():
    usecase, broadcaster = _make()

    await usecase.handle(_button("R1", 1))

    assert broadcaster.messages == [
        {"type": "control:flipper", "side": "right", "action": "press"}
    ]


# --- plunger ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_plunger_charge_then_release():
    usecase, broadcaster = _make()

    await usecase.handle(MqttEvent(topic=PLUNGER_TOPIC, payload={"state": 1, "ts": 1}))
    await usecase.handle(MqttEvent(topic=PLUNGER_TOPIC, payload={"state": 0, "ts": 2}))

    assert broadcaster.messages == [
        {"type": "control:plunger", "action": "charge"},
        {"type": "control:plunger", "action": "release"},
    ]


# --- navigation (relais brut, orienté côté front) ---------------------------


@pytest.mark.parametrize(
    "button_id,expected",
    [
        ("top", "confirm"),
        ("bottom", "back"),
        ("L2", "left"),
        ("R2", "right"),
        ("middle", "help"),
    ],
)
@pytest.mark.asyncio
async def test_nav_buttons_are_relayed_as_control_nav(button_id, expected):
    usecase, broadcaster = _make()

    await usecase.handle(_button(button_id, 1))

    assert broadcaster.messages == [{"type": "control:nav", "button": expected}]


@pytest.mark.asyncio
async def test_nav_buttons_act_on_press_only():
    usecase, broadcaster = _make()

    await usecase.handle(_button("top", 0))  # release → ignoré

    assert broadcaster.messages == []


# --- robustesse -------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_button_id_is_ignored():
    usecase, broadcaster = _make()

    await usecase.handle(_button("does-not-exist", 1))

    assert broadcaster.messages == []


@pytest.mark.asyncio
async def test_malformed_payload_is_ignored():
    usecase, broadcaster = _make()

    await usecase.handle(MqttEvent(topic=BUTTON_TOPIC, payload={"id": "L1"}))  # pas de state
    await usecase.handle(MqttEvent(topic=BUTTON_TOPIC, payload={"state": 1}))  # pas d'id

    assert broadcaster.messages == []
