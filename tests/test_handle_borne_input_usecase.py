import pytest

from app.domain.borne import Borne, BorneNavState
from app.domain.ports.borne_store import BorneStore
from app.domain.ports.mqtt_gateway import MqttEvent
from app.usecase.handle_borne_input_usecase import HandleBorneInputUseCase

BORNE_ID = "borne-test"
BUTTON_TOPIC = "pinball/esp32-test/input/button"
PLUNGER_TOPIC = "pinball/esp32-test/input/plunger"


class FakeBorneStore(BorneStore):
    def __init__(self, initial: Borne | None = None):
        self._bornes: dict[str, Borne] = {}
        if initial is not None:
            self._bornes[initial.borne_id] = initial

    async def get_or_create(self, borne_id: str) -> Borne:
        if borne_id not in self._bornes:
            self._bornes[borne_id] = Borne(borne_id=borne_id)
        return self._bornes[borne_id]

    async def update(self, borne: Borne) -> None:
        self._bornes[borne.borne_id] = borne


class RecordingBroadcaster:
    def __init__(self):
        self.messages: list[dict] = []

    async def broadcast_to_borne(self, borne_id: str, message: dict) -> None:
        self.messages.append(message)

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        self.messages.append(message)


class RecordingApplyIntent:
    """Capture les appels nav sans rejouer la logique (testée ailleurs)."""

    def __init__(self):
        self.intents: list[str] = []
        self.commands: list[str] = []

    async def execute(self, borne_id: str, action: str, payload=None) -> None:
        self.intents.append(action)

    async def handle_match_command(self, borne_id: str, cmd_type: str) -> None:
        self.commands.append(cmd_type)


def _make(nav: BorneNavState = BorneNavState.SPLASH):
    store = FakeBorneStore(Borne(borne_id=BORNE_ID, nav=nav))
    broadcaster = RecordingBroadcaster()
    apply_intent = RecordingApplyIntent()
    usecase = HandleBorneInputUseCase(BORNE_ID, store, broadcaster, apply_intent)
    return usecase, broadcaster, apply_intent


def _button(button_id: str, state: int) -> MqttEvent:
    return MqttEvent(topic=BUTTON_TOPIC, payload={"id": button_id, "state": state, "ts": 1})


# --- flippers ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_left_flipper_press_and_release_are_broadcast():
    usecase, broadcaster, _ = _make()

    await usecase.handle(_button("L1", 1))
    await usecase.handle(_button("L1", 0))

    assert broadcaster.messages == [
        {"type": "control:flipper", "side": "left", "action": "press"},
        {"type": "control:flipper", "side": "left", "action": "release"},
    ]


@pytest.mark.asyncio
async def test_right_flipper_maps_to_right_side():
    usecase, broadcaster, _ = _make()

    await usecase.handle(_button("R1", 1))

    assert broadcaster.messages == [
        {"type": "control:flipper", "side": "right", "action": "press"}
    ]


# --- plunger ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_plunger_charge_then_release():
    usecase, broadcaster, _ = _make()

    await usecase.handle(MqttEvent(topic=PLUNGER_TOPIC, payload={"state": 1, "ts": 1}))
    await usecase.handle(MqttEvent(topic=PLUNGER_TOPIC, payload={"state": 0, "ts": 2}))

    assert broadcaster.messages == [
        {"type": "control:plunger", "action": "charge"},
        {"type": "control:plunger", "action": "release"},
    ]


# --- navigation (résolution contextuelle) -----------------------------------


@pytest.mark.asyncio
async def test_confirm_in_splash_presses_a():
    usecase, _, apply_intent = _make(BorneNavState.SPLASH)

    await usecase.handle(_button("top", 1))

    assert apply_intent.intents == ["PRESS_A"]


@pytest.mark.asyncio
async def test_confirm_in_menu_starts_game():
    usecase, _, apply_intent = _make(BorneNavState.MENU)

    await usecase.handle(_button("top", 1))

    assert apply_intent.intents == ["START_GAME"]


@pytest.mark.asyncio
async def test_back_in_identification_returns_to_menu():
    usecase, _, apply_intent = _make(BorneNavState.IDENTIFICATION)

    await usecase.handle(_button("bottom", 1))

    assert apply_intent.intents == ["BACK_TO_MENU"]


@pytest.mark.asyncio
async def test_back_in_game_pauses_the_match():
    usecase, _, apply_intent = _make(BorneNavState.IN_GAME)

    await usecase.handle(_button("bottom", 1))

    assert apply_intent.commands == ["cmd:pause"]
    assert apply_intent.intents == []


@pytest.mark.asyncio
async def test_nav_buttons_act_on_press_only():
    usecase, _, apply_intent = _make(BorneNavState.SPLASH)

    await usecase.handle(_button("top", 0))  # release → ignoré

    assert apply_intent.intents == []


@pytest.mark.asyncio
async def test_directional_buttons_are_noop_for_now():
    usecase, broadcaster, apply_intent = _make(BorneNavState.MENU)

    await usecase.handle(_button("L2", 1))
    await usecase.handle(_button("R2", 1))

    assert apply_intent.intents == []
    assert apply_intent.commands == []
    assert broadcaster.messages == []


# --- robustesse -------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_button_id_is_ignored():
    usecase, broadcaster, apply_intent = _make()

    await usecase.handle(_button("does-not-exist", 1))

    assert broadcaster.messages == []
    assert apply_intent.intents == []


@pytest.mark.asyncio
async def test_malformed_payload_is_ignored():
    usecase, broadcaster, apply_intent = _make()

    await usecase.handle(MqttEvent(topic=BUTTON_TOPIC, payload={"id": "L1"}))  # pas de state
    await usecase.handle(MqttEvent(topic=BUTTON_TOPIC, payload={"state": 1}))  # pas d'id

    assert broadcaster.messages == []
    assert apply_intent.intents == []
