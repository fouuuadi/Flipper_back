class DomainError(Exception):
    pass


class PlayerNotFoundError(DomainError):
    pass


class PlayerAlreadyExistsError(DomainError):
    pass


class RoomNotFoundError(DomainError):
    pass


class GameNotFoundError(DomainError):
    pass


class GameAlreadyFinishedError(DomainError):
    pass


class GameNotPlayableError(DomainError):
    pass


class SessionNotFoundError(DomainError):
    pass


class InvalidPseudoError(DomainError):
    pass


class MatchmakingNotFoundError(DomainError):
    pass


class InvalidMatchmakingModeError(DomainError):
    pass
