from app.domain.game_event import GameEvent, GameEventType
from app.domain.ports.game_event_repository import GameEventRepository
from app.infrastructure.db._executor import Executor, acquire
from app.infrastructure.db.mappers.game_event_mapper import row_to_game_event


class PgGameEventRepository(GameEventRepository):
    """asyncpg-backed repository for game events.

    Accepts either an `asyncpg.Pool` or a single `asyncpg.Connection`
    (when running inside a `UnitOfWork`).
    """

    def __init__(self, executor: Executor):
        self._executor = executor

    async def create(
        self, game_id: int, type: GameEventType, points: int = 0
    ) -> GameEvent:
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                "INSERT INTO game_events (game_id, type, points) VALUES ($1, $2, $3) "
                "RETURNING id, game_id, type, points, occured_at",
                game_id,
                type.value,
                points,
            )
        return row_to_game_event(dict(row))

    async def get_by_id(self, id: int) -> GameEvent | None:
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                "SELECT id, game_id, type, points, occured_at "
                "FROM game_events WHERE id = $1",
                id,
            )
        return row_to_game_event(dict(row) if row is not None else None)

    async def get_by_game_id(self, game_id: int, limit: int = 10) -> list[GameEvent]:
        async with acquire(self._executor) as conn:
            rows = await conn.fetch(
                "SELECT id, game_id, type, points, occured_at FROM game_events "
                "WHERE game_id = $1 ORDER BY occured_at DESC, id DESC LIMIT $2",
                game_id,
                limit,
            )
        return [row_to_game_event(dict(r)) for r in rows]
