import pytest

from app.transport.ws.handler import _handle_borne_intent

BORNE_ID = "borne-1"


class FakeApplyIntent:
    """Duck-type d'ApplyBorneIntentUseCase : enregistre les appels."""

    def __init__(self):
        self.intents: list[tuple[str, str, dict | None]] = []
        self.commands: list[tuple[str, str]] = []

    async def execute(self, borne_id: str, action: str, payload=None) -> None:
        self.intents.append((borne_id, action, payload))

    async def handle_match_command(self, borne_id: str, cmd_type: str) -> None:
        self.commands.append((borne_id, cmd_type))


@pytest.mark.asyncio
async def test_valid_intent_routes_to_usecase():
    uc = FakeApplyIntent()
    await _handle_borne_intent('{"type": "intent", "action": "PRESS_A"}', BORNE_ID, uc)
    assert uc.intents == [(BORNE_ID, "PRESS_A", None)]
    assert uc.commands == []


@pytest.mark.asyncio
async def test_intent_payload_is_forwarded():
    uc = FakeApplyIntent()
    raw = '{"type": "intent", "action": "PLAYERS_VALIDATED", "payload": {"pseudo": "ABC"}}'
    await _handle_borne_intent(raw, BORNE_ID, uc)
    assert uc.intents == [(BORNE_ID, "PLAYERS_VALIDATED", {"pseudo": "ABC"})]


@pytest.mark.asyncio
@pytest.mark.parametrize("cmd", ["cmd:pause", "cmd:resume", "cmd:abandon"])
async def test_match_commands_route_to_handle_match_command(cmd):
    uc = FakeApplyIntent()
    await _handle_borne_intent(f'{{"type": "{cmd}"}}', BORNE_ID, uc)
    assert uc.commands == [(BORNE_ID, cmd)]
    assert uc.intents == []


@pytest.mark.asyncio
async def test_invalid_json_is_dropped():
    uc = FakeApplyIntent()
    await _handle_borne_intent("{not json", BORNE_ID, uc)
    assert uc.intents == [] and uc.commands == []


@pytest.mark.asyncio
async def test_non_object_payload_is_dropped():
    uc = FakeApplyIntent()
    await _handle_borne_intent('"just a string"', BORNE_ID, uc)
    assert uc.intents == [] and uc.commands == []


@pytest.mark.asyncio
async def test_intent_without_action_is_dropped():
    uc = FakeApplyIntent()
    await _handle_borne_intent('{"type": "intent"}', BORNE_ID, uc)
    assert uc.intents == [] and uc.commands == []


@pytest.mark.asyncio
async def test_unknown_type_is_dropped():
    uc = FakeApplyIntent()
    await _handle_borne_intent('{"type": "garbage"}', BORNE_ID, uc)
    assert uc.intents == [] and uc.commands == []
