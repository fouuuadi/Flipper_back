import io
import json
import logging

import pytest

from app.logging_config import JsonFormatter, configure_logging


def _make_record(level: int = logging.INFO, msg: str = "hi", **extras) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=None,
        exc_info=None,
    )
    for key, value in extras.items():
        setattr(record, key, value)
    return record


def test_formatter_emits_standard_fields():
    formatted = JsonFormatter().format(_make_record(msg="hello"))
    payload = json.loads(formatted)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "hello"
    assert payload["timestamp"].endswith("Z")


def test_formatter_includes_extra_fields():
    formatted = JsonFormatter().format(
        _make_record(msg="http_request", request_id="abc", duration_ms=12.5)
    )
    payload = json.loads(formatted)
    assert payload["request_id"] == "abc"
    assert payload["duration_ms"] == 12.5


def test_formatter_serialises_exception_info():
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=None,
            exc_info=True,
        )
        import sys

        record.exc_info = sys.exc_info()

    formatted = JsonFormatter().format(record)
    payload = json.loads(formatted)
    assert "exc_info" in payload
    assert "ValueError" in payload["exc_info"]
    assert "boom" in payload["exc_info"]


def test_formatter_message_supports_args():
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Connected (attempt %d/%d)",
        args=(2, 10),
        exc_info=None,
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "Connected (attempt 2/10)"


def test_configure_logging_installs_single_json_handler():
    configure_logging("DEBUG")
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
    assert root.level == logging.DEBUG


def test_configure_logging_is_idempotent():
    configure_logging("INFO")
    configure_logging("INFO")
    configure_logging("WARNING")
    assert len(logging.getLogger().handlers) == 1
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_writes_json_to_stdout(capsys):
    configure_logging("INFO")
    # Force the handler to write into capsys-captured stream.
    handler = logging.getLogger().handlers[0]
    buffer = io.StringIO()
    handler.stream = buffer

    logging.getLogger("app.demo").info("ping", extra={"foo": "bar"})

    handler.flush()
    output = buffer.getvalue().strip()
    payload = json.loads(output)
    assert payload["message"] == "ping"
    assert payload["foo"] == "bar"
    assert payload["logger"] == "app.demo"


@pytest.fixture(autouse=True)
def restore_logging():
    """Reset root logger after each test to keep them isolated."""
    original_handlers = logging.getLogger().handlers[:]
    original_level = logging.getLogger().level
    yield
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in original_handlers:
        root.addHandler(handler)
    root.setLevel(original_level)
