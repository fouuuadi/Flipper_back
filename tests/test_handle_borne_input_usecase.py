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


# --- navigation : une seule action à l'appui, rien au relâchement ------------


@pytest.mark.parametrize(
    "button_id,expected",
    [("top", "confirm"), ("bottom", "back"), ("L2", "left"), ("R1", "right"), ("middle", "help")],
)
@pytest.mark.asyncio
async def test_nav_relayed_once_on_press(button_id, expected):
    usecase, broadcaster = _make()

    await usecase.handle(_button(button_id, state=1))

    assert broadcaster.messages == [{"type": "control:nav", "button": expected}]


@pytest.mark.asyncio
async def test_nav_release_is_ignored():
    # Le firmware envoie state=0 au relâchement : il ne doit pas rejouer l'action.
    usecase, broadcaster = _make()

    await usecase.handle(_button("L2", state=0))

    assert broadcaster.messages == []


# --- flippers : relais direct de l'état (boutons blancs) --------------------


@pytest.mark.asyncio
async def test_left_flipper_follows_button_state():
    usecase, broadcaster = _make()

    await usecase.handle(_button("L1", state=1))
    await usecase.handle(_button("L1", state=0))

    assert broadcaster.messages == [
        {"type": "control:flipper", "side": "left", "action": "press"},
        {"type": "control:flipper", "side": "left", "action": "release"},
    ]


@pytest.mark.asyncio
async def test_right_flipper_is_white_right_button():
    # R2 = bouton blanc droit → flipper droit (symétrie avec L1/blanc gauche).
    usecase, broadcaster = _make()

    await usecase.handle(_button("R2", state=1))
    await usecase.handle(_button("R2", state=0))

    assert broadcaster.messages == [
        {"type": "control:flipper", "side": "right", "action": "press"},
        {"type": "control:flipper", "side": "right", "action": "release"},
    ]


# --- plunger : relais direct de l'état --------------------------------------


@pytest.mark.asyncio
async def test_plunger_follows_state():
    usecase, broadcaster = _make()

    await usecase.handle(MqttEvent(topic=PLUNGER_TOPIC, payload={"state": 1, "ts": 1}))
    await usecase.handle(MqttEvent(topic=PLUNGER_TOPIC, payload={"state": 0, "ts": 1}))

    assert broadcaster.messages == [
        {"type": "control:plunger", "action": "charge"},
        {"type": "control:plunger", "action": "release"},
    ]


# --- robustesse -------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_button_is_ignored():
    usecase, broadcaster = _make()

    await usecase.handle(_button("does-not-exist", state=1))

    assert broadcaster.messages == []


@pytest.mark.asyncio
async def test_malformed_payload_is_ignored():
    usecase, broadcaster = _make()

    await usecase.handle(MqttEvent(topic=BUTTON_TOPIC, payload={"state": 1}))

    assert broadcaster.messages == []
