from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    DomainError,
    GameAlreadyFinishedError,
    GameNotFoundError,
    GameNotPlayableError,
    InvalidPseudoError,
    PlayerAlreadyExistsError,
    PlayerNotFoundError,
    RoomNotFoundError,
    SessionNotFoundError,
)

_NOT_FOUND_EXCEPTIONS = (
    PlayerNotFoundError,
    RoomNotFoundError,
    GameNotFoundError,
    SessionNotFoundError,
)

_CONFLICT_EXCEPTIONS = (
    PlayerAlreadyExistsError,
    GameAlreadyFinishedError,
    GameNotPlayableError,
)

_UNPROCESSABLE_EXCEPTIONS = (InvalidPseudoError,)


def _to_response(status_code: int, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": exc.__class__.__name__, "detail": str(exc)},
    )


async def _not_found_handler(_: Request, exc: Exception) -> JSONResponse:
    return _to_response(404, exc)


async def _conflict_handler(_: Request, exc: Exception) -> JSONResponse:
    return _to_response(409, exc)


async def _domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return _to_response(400, exc)


async def _unprocessable_handler(_: Request, exc: Exception) -> JSONResponse:
    return _to_response(422, exc)


def register_error_handlers(app: FastAPI) -> None:
    for exc_cls in _NOT_FOUND_EXCEPTIONS:
        app.add_exception_handler(exc_cls, _not_found_handler)
    for exc_cls in _CONFLICT_EXCEPTIONS:
        app.add_exception_handler(exc_cls, _conflict_handler)
    for exc_cls in _UNPROCESSABLE_EXCEPTIONS:
        app.add_exception_handler(exc_cls, _unprocessable_handler)
    app.add_exception_handler(DomainError, _domain_error_handler)
