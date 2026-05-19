import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.domain.exceptions import (
    DomainError,
    GameAlreadyFinishedError,
    GameNotFoundError,
    GameNotPlayableError,
    PlayerAlreadyExistsError,
    PlayerNotFoundError,
    RoomNotFoundError,
)
from app.transport.http.error_handler import register_error_handlers


def _make_app(exc: Exception) -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom():
        raise exc

    return app


async def _call(app: FastAPI):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/boom")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_cls",
    [PlayerNotFoundError, RoomNotFoundError, GameNotFoundError],
)
async def test_not_found_exceptions_return_404(exc_cls):
    response = await _call(_make_app(exc_cls("missing")))
    assert response.status_code == 404
    assert response.json() == {"error": exc_cls.__name__, "detail": "missing"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_cls",
    [PlayerAlreadyExistsError, GameAlreadyFinishedError, GameNotPlayableError],
)
async def test_conflict_exceptions_return_409(exc_cls):
    response = await _call(_make_app(exc_cls("conflict")))
    assert response.status_code == 409
    assert response.json() == {"error": exc_cls.__name__, "detail": "conflict"}


@pytest.mark.asyncio
async def test_generic_domain_error_returns_400():
    response = await _call(_make_app(DomainError("bad input")))
    assert response.status_code == 400
    assert response.json() == {"error": "DomainError", "detail": "bad input"}


@pytest.mark.asyncio
async def test_non_domain_exception_is_not_caught():
    """Les exceptions non-DomainError remontent sans être attrapées par les handlers."""
    with pytest.raises(RuntimeError, match="boom"):
        await _call(_make_app(RuntimeError("boom")))
