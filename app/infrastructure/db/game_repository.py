from datetime import datetime
from typing import Any

import aiomysql

from app.domain.game import Game, GameMode, GameStatus
from app.domain.game_event import GameEventType
from app.domain.leaderboard_entry import LeaderboardEntry
from app.domain.ports.game_repository import GameRepository
from app.infrastructure.db.mappers.game_mapper import row_to_game

_TOPIC_TO_EVENT_TYPE: dict[str, GameEventType] = {
    "flipper/bumper/hit": GameEventType.BUMPER_HIT,
    "flipper/bonus": GameEventType.BONUS,
    "flipper/ball/lost": GameEventType.BALL_LOST,
    "flipper/flipper/hit": GameEventType.FLIPPER_HIT,
    "flipper/game/over": GameEventType.GAME_OVER,
}


class MysqlGameRepository(GameRepository):
    """
    Repository pour gérer les opérations CRUD sur les games.
    """

    def __init__(self, pool: aiomysql.Pool):
        self.pool = pool

    async def create(self, player_id: int, room_id: int | None, mode: GameMode) -> Game:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO games (player_id, room_id, mode, score, status) VALUES (%s, %s, %s, %s, %s)",
                    (player_id, room_id, mode.value, 0, GameStatus.PLAYING.value),
                )
                game_id = cursor.lastrowid
                await conn.commit()

            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (game_id,),
                )
                return row_to_game(await cursor.fetchone())

    async def get_by_id(self, id: int) -> Game | None:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (id,),
                )
                return row_to_game(await cursor.fetchone())

    async def add_points(self, game_id: int, points: int) -> Game:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE games SET score = score + %s WHERE id = %s",
                    (points, game_id),
                )
                await conn.commit()

            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (game_id,),
                )
                return row_to_game(await cursor.fetchone())

    async def get_active_by_room(self, room_id: int) -> list[Game]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE room_id = %s AND status = %s",
                    (room_id, GameStatus.PLAYING.value),
                )
                rows = await cursor.fetchall()
                return [row_to_game(row) for row in rows]

    async def finish(self, game_id: int) -> Game:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE games SET status = %s, finished_at = NOW() WHERE id = %s",
                    (GameStatus.FINISHED.value, game_id),
                )
                await conn.commit()

            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE id = %s",
                    (game_id,),
                )
                return row_to_game(await cursor.fetchone())

    async def leaderboard(
        self,
        mode: GameMode | None,
        limit: int,
    ) -> list[LeaderboardEntry]:
        sql = (
            "SELECT p.id AS player_id, p.pseudo AS pseudo, MAX(g.score) AS score "
            "FROM games g "
            "JOIN players p ON g.player_id = p.id "
            "WHERE g.status = %s"
        )
        params: list = [GameStatus.FINISHED.value]
        if mode is not None:
            sql += " AND g.mode = %s"
            params.append(mode.value)
        sql += " GROUP BY p.id, p.pseudo ORDER BY score DESC, p.id ASC LIMIT %s"
        params.append(int(limit))

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, tuple(params))
                rows = await cursor.fetchall()
        return [
            LeaderboardEntry(
                rank=index,
                player_id=row["player_id"],
                pseudo=row["pseudo"],
                score=int(row["score"]),
            )
            for index, row in enumerate(rows, start=1)
        ]

    async def get_by_status(self, status: GameStatus) -> list[Game]:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at FROM games WHERE status = %s ORDER BY started_at DESC",
                    (status.value,),
                )
                rows = await cursor.fetchall()
                return [row_to_game(row) for row in rows]

    async def get_finished_games_by_player(
        self,
        player_id: int,
        mode: GameMode | None,
        limit: int,
    ) -> list[Game]:
        sql = (
            "SELECT id, match_id, player_id, room_id, mode, score, status, started_at, finished_at "
            "FROM games "
            "WHERE player_id = %s AND status = %s"
        )
        params: list = [player_id, GameStatus.FINISHED.value]
        if mode is not None:
            sql += " AND mode = %s"
            params.append(mode.value)
        sql += " ORDER BY finished_at DESC, id DESC LIMIT %s"
        params.append(int(limit))

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, tuple(params))
                rows = await cursor.fetchall()
        return [row_to_game(row) for row in rows]

    async def get_best_solo_score(self, player_id: int) -> int | None:
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT MAX(score) AS best FROM games "
                    "WHERE player_id = %s AND mode = %s AND status = %s",
                    (player_id, GameMode.SOLO.value, GameStatus.FINISHED.value),
                )
                row = await cursor.fetchone()
        if row is None or row["best"] is None:
            return None
        return int(row["best"])

    async def persist_finished_session(
        self,
        pseudo: str,
        mode: GameMode,
        score: int,
        started_at: datetime,
        finished_at: datetime,
        events: list[dict[str, Any]],
    ) -> tuple[int, int, int]:
        event_rows = self._build_event_rows(events)
        async with self.pool.acquire() as conn:
            try:
                await conn.begin()
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    player_id = await self._upsert_player(cursor, pseudo)
                    game_id = await self._insert_finished_game(
                        cursor, player_id, mode, score, started_at, finished_at
                    )
                    inserted_events = await self._insert_event_rows(cursor, game_id, event_rows)
                await conn.commit()
                return player_id, game_id, inserted_events
            except Exception:
                await conn.rollback()
                raise

    @staticmethod
    def _build_event_rows(events: list[dict[str, Any]]) -> list[tuple]:
        rows: list[tuple] = []
        for ev in events:
            topic = ev.get("topic")
            event_type = _TOPIC_TO_EVENT_TYPE.get(topic) if isinstance(topic, str) else None
            if event_type is None:
                continue
            payload = ev.get("payload") or {}
            try:
                points = int(payload.get("points", 0))
            except (TypeError, ValueError):
                points = 0
            occured_at = ev.get("occured_at")
            if isinstance(occured_at, str):
                try:
                    occured_at = datetime.fromisoformat(occured_at)
                except ValueError:
                    occured_at = datetime.utcnow()
            elif not isinstance(occured_at, datetime):
                occured_at = datetime.utcnow()
            rows.append((event_type.value, points, occured_at))
        return rows

    @staticmethod
    async def _upsert_player(cursor, pseudo: str) -> int:
        await cursor.execute("SELECT id FROM players WHERE pseudo = %s", (pseudo,))
        row = await cursor.fetchone()
        if row:
            return row["id"]
        await cursor.execute("INSERT INTO players (pseudo) VALUES (%s)", (pseudo,))
        return cursor.lastrowid

    @staticmethod
    async def _insert_finished_game(
        cursor,
        player_id: int,
        mode: GameMode,
        score: int,
        started_at: datetime,
        finished_at: datetime,
    ) -> int:
        await cursor.execute(
            "INSERT INTO games (player_id, room_id, mode, score, status, started_at, finished_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                player_id,
                None,
                mode.value,
                score,
                GameStatus.FINISHED.value,
                started_at,
                finished_at,
            ),
        )
        return cursor.lastrowid

    @staticmethod
    async def _insert_event_rows(cursor, game_id: int, event_rows: list[tuple]) -> int:
        if not event_rows:
            return 0
        rows_with_game = [(game_id,) + row for row in event_rows]
        await cursor.executemany(
            "INSERT INTO game_events (game_id, type, points, occured_at) VALUES (%s, %s, %s, %s)",
            rows_with_game,
        )
        return len(rows_with_game)
