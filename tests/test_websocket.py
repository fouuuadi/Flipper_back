import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.transport.ws.handler import hub


def test_websocket_broadcast_to_two_clients():
    client = TestClient(app)

    with client.websocket_connect("/ws") as ws1, client.websocket_connect("/ws") as ws2:
        assert hub.count() == 2

        ws1.send_json({"type": "input", "payload": {"key": "left"}})

        msg1 = ws1.receive_json()
        msg2 = ws2.receive_json()

        assert msg1["type"] == "input"
        assert msg1["payload"] == {"key": "left"}
        assert "timestamp" in msg1

        assert msg2["type"] == "input"
        assert msg2["payload"] == {"key": "left"}
        assert "timestamp" in msg2


def test_websocket_disconnect():
    client = TestClient(app)

    with client.websocket_connect("/ws"):
        assert hub.count() == 1

    assert hub.count() == 0
