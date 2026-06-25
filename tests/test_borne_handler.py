import json

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


class FakeBorneHubManager:
    """Duck-type du borne hub manager : enregistre les broadcasts."""

    def __init__(self):
        self.broadcasts: list[tuple[str, dict]] = []

    async def broadcast_to_borne(self, borne_id: str, message: dict) -> None:
        self.broadcasts.append((borne_id, message))


class FakeFinishFromRelay:
    """Duck-type de FinishBorneGameFromRelayUseCase : enregistre les game over."""

    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    async def execute(self, borne_id: str, final_score: object) -> None:
        self.calls.append((borne_id, final_score))


def _deps():
    return FakeApplyIntent(), FakeBorneHubManager(), FakeFinishFromRelay()


@pytest.mark.asyncio
async def test_valid_intent_routes_to_usecase():
    uc, hub, finisher = _deps()
    await _handle_borne_intent('{"type": "intent", "action": "PRESS_A"}', BORNE_ID, uc, hub, finisher)
    assert uc.intents == [(BORNE_ID, "PRESS_A", None)]
    assert uc.commands == [] and hub.broadcasts == [] and finisher.calls == []


@pytest.mark.asyncio
async def test_intent_payload_is_forwarded():
    uc, hub, finisher = _deps()
    raw = '{"type": "intent", "action": "PLAYERS_VALIDATED", "payload": {"pseudo": "ABC"}}'
    await _handle_borne_intent(raw, BORNE_ID, uc, hub, finisher)
    assert uc.intents == [(BORNE_ID, "PLAYERS_VALIDATED", {"pseudo": "ABC"})]


@pytest.mark.asyncio
@pytest.mark.parametrize("cmd", ["cmd:pause", "cmd:resume", "cmd:abandon"])
async def test_match_commands_route_to_handle_match_command(cmd):
    uc, hub, finisher = _deps()
    await _handle_borne_intent(f'{{"type": "{cmd}"}}', BORNE_ID, uc, hub, finisher)
    assert uc.commands == [(BORNE_ID, cmd)]
    assert uc.intents == []


# --- relais des events de jeu poussés par le playfield ----------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event",
    [
        {"type": "score:update", "score": 750, "combo": 1},
        {"type": "ball:lost", "livesRemaining": 2},
        {"type": "game:over", "finalScore": 4200},
        {"type": "match:state", "status": "over", "sessionId": None},
    ],
)
async def test_relay_broadcasts_allowed_event_to_borne(event):
    uc, hub, finisher = _deps()
    raw = json.dumps({"type": "borne:relay", "event": event})
    await _handle_borne_intent(raw, BORNE_ID, uc, hub, finisher)
    assert hub.broadcasts == [(BORNE_ID, event)]
    assert uc.intents == [] and uc.commands == []


@pytest.mark.asyncio
async def test_relay_game_over_persists_with_final_score():
    # Le playfield est l'autorité du game over : le relais doit persister le run
    # (score final → BDD/leaderboard) et basculer la nav.
    uc, hub, finisher = _deps()
    raw = json.dumps({"type": "borne:relay", "event": {"type": "game:over", "finalScore": 4200}})
    await _handle_borne_intent(raw, BORNE_ID, uc, hub, finisher)
    assert finisher.calls == [(BORNE_ID, 4200)]
    assert hub.broadcasts == [(BORNE_ID, {"type": "game:over", "finalScore": 4200})]


@pytest.mark.asyncio
async def test_relay_score_update_does_not_finish_game():
    uc, hub, finisher = _deps()
    raw = json.dumps({"type": "borne:relay", "event": {"type": "score:update", "score": 10, "combo": 1}})
    await _handle_borne_intent(raw, BORNE_ID, uc, hub, finisher)
    assert finisher.calls == []


@pytest.mark.asyncio
async def test_relay_rejects_event_type_not_in_allowlist():
    uc, hub, finisher = _deps()
    raw = '{"type": "borne:relay", "event": {"type": "nav:state", "nav": "menu"}}'
    await _handle_borne_intent(raw, BORNE_ID, uc, hub, finisher)
    assert hub.broadcasts == [] and finisher.calls == []


@pytest.mark.asyncio
async def test_relay_without_event_is_dropped():
    uc, hub, finisher = _deps()
    await _handle_borne_intent('{"type": "borne:relay"}', BORNE_ID, uc, hub, finisher)
    assert hub.broadcasts == [] and finisher.calls == []


# --- robustesse -------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_json_is_dropped():
    uc, hub, finisher = _deps()
    await _handle_borne_intent("{not json", BORNE_ID, uc, hub, finisher)
    assert uc.intents == [] and uc.commands == [] and hub.broadcasts == []


@pytest.mark.asyncio
async def test_non_object_payload_is_dropped():
    uc, hub, finisher = _deps()
    await _handle_borne_intent('"just a string"', BORNE_ID, uc, hub, finisher)
    assert uc.intents == [] and uc.commands == [] and hub.broadcasts == []


@pytest.mark.asyncio
async def test_intent_without_action_is_dropped():
    uc, hub, finisher = _deps()
    await _handle_borne_intent('{"type": "intent"}', BORNE_ID, uc, hub, finisher)
    assert uc.intents == [] and uc.commands == []


@pytest.mark.asyncio
async def test_unknown_type_is_dropped():
    uc, hub, finisher = _deps()
    await _handle_borne_intent('{"type": "garbage"}', BORNE_ID, uc, hub, finisher)
    assert uc.intents == [] and uc.commands == [] and hub.broadcasts == []
