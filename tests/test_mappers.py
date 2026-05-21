from datetime import datetime

from app.domain.game import GameMode, GameStatus
from app.domain.game_event import GameEventType
from app.domain.room import RoomStatus
from app.infrastructure.db.mappers.game_event_mapper import row_to_game_event
from app.infrastructure.db.mappers.game_mapper import row_to_game
from app.infrastructure.db.mappers.player_mapper import row_to_player
from app.infrastructure.db.mappers.room_mapper import row_to_room


def test_row_to_player_none_returns_none():
    assert row_to_player(None) is None


def test_row_to_player_maps_all_fields():
    now = datetime(2026, 5, 21, 12, 0, 0)
    row = {"id": 7, "pseudo": "fouad", "created_at": now}

    player = row_to_player(row)

    assert player.id == 7
    assert player.pseudo == "fouad"
    assert player.created_at == now


def test_row_to_room_none_returns_none():
    assert row_to_room(None) is None


def test_row_to_room_converts_enums_from_strings():
    now = datetime(2026, 5, 21, 12, 0, 0)
    row = {
        "id": 3,
        "code": "ABC123",
        "mode": "solo",
        "status": "waiting",
        "created_at": now,
    }

    room = row_to_room(row)

    assert room.id == 3
    assert room.code == "ABC123"
    assert room.mode == GameMode.SOLO
    assert room.status == RoomStatus.WAITING
    assert room.created_at == now


def test_row_to_game_none_returns_none():
    assert row_to_game(None) is None


def test_row_to_game_maps_nullable_fields_and_enums():
    started = datetime(2026, 5, 21, 12, 0, 0)
    row = {
        "id": 42,
        "match_id": None,
        "player_id": 7,
        "room_id": None,
        "mode": "1v1",
        "score": 150,
        "status": "playing",
        "started_at": started,
        "finished_at": None,
    }

    game = row_to_game(row)

    assert game.id == 42
    assert game.match_id is None
    assert game.player_id == 7
    assert game.room_id is None
    assert game.mode == GameMode.ONE_V_ONE
    assert game.score == 150
    assert game.status == GameStatus.PLAYING
    assert game.started_at == started
    assert game.finished_at is None


def test_row_to_game_finished_carries_finished_at():
    started = datetime(2026, 5, 21, 12, 0, 0)
    finished = datetime(2026, 5, 21, 12, 5, 0)
    row = {
        "id": 1,
        "match_id": None,
        "player_id": 1,
        "room_id": 1,
        "mode": "solo",
        "score": 0,
        "status": "finished",
        "started_at": started,
        "finished_at": finished,
    }

    game = row_to_game(row)

    assert game.status == GameStatus.FINISHED
    assert game.finished_at == finished


def test_row_to_game_event_none_returns_none():
    assert row_to_game_event(None) is None


def test_row_to_game_event_maps_type_enum():
    occured = datetime(2026, 5, 21, 12, 0, 0)
    row = {
        "id": 11,
        "game_id": 42,
        "type": "bumper_hit",
        "points": 100,
        "occured_at": occured,
    }

    event = row_to_game_event(row)

    assert event.id == 11
    assert event.game_id == 42
    assert event.type == GameEventType.BUMPER_HIT
    assert event.points == 100
    assert event.occured_at == occured
