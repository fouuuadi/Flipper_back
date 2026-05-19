from app.domain.exceptions import (
    DomainError,
    GameAlreadyFinishedError,
    GameNotFoundError,
    GameNotPlayableError,
    PlayerAlreadyExistsError,
    PlayerNotFoundError,
    RoomNotFoundError,
)


def test_all_exceptions_inherit_from_domain_error():
    """Toutes les exceptions métier héritent de DomainError."""
    for exc_cls in (
        PlayerNotFoundError,
        PlayerAlreadyExistsError,
        RoomNotFoundError,
        GameNotFoundError,
        GameAlreadyFinishedError,
        GameNotPlayableError,
    ):
        assert issubclass(exc_cls, DomainError)


def test_domain_error_inherits_from_exception():
    """DomainError reste une Exception standard."""
    assert issubclass(DomainError, Exception)


def test_exceptions_carry_message():
    """Le message passé au constructeur est conservé dans str()."""
    err = GameNotFoundError("Game 42 introuvable")
    assert "42" in str(err)
