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
