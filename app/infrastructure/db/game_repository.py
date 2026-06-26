from datetime import datetime
from typing import Any

import asyncpg

from app.domain.game import Game, GameMode, GameStatus
from app.domain.game_event import GameEventType
from app.domain.leaderboard_entry import LeaderboardEntry
from app.domain.ports.game_repository import GameRepository
from app.infrastructure.db._executor import Executor, acquire
from app.infrastructure.db.mappers.game_mapper import row_to_game

# Traduction topic MQTT → type d'event persisté. Sert à rejouer le buffer Redis
# d'une partie vers la table game_events à la fin du match. À garder synchro avec
# les topics publiés côté capteurs : un topic absent d'ici est ignoré au flush
# (cf. _build_event_rows), donc l'event ne sera jamais enregistré en base.
_TOPIC_TO_EVENT_TYPE: dict[str, GameEventType] = {
    "flipper/bumper/hit": GameEventType.BUMPER_HIT,
    "flipper/bonus": GameEventType.BONUS,
    "flipper/ball/lost": GameEventType.BALL_LOST,
    "flipper/flipper/hit": GameEventType.FLIPPER_HIT,
    "flipper/game/over": GameEventType.GAME_OVER,
}

_GAME_SELECT_COLS = (
    "id, match_id, player_id, room_id, mode, score, status, started_at, finished_at"
)


class PgGameRepository(GameRepository):
    """Repository des parties, sur asyncpg (SQL brut, pas d'ORM).

    Accepte soit un `asyncpg.Pool` (usage autonome), soit une `asyncpg.Connection`
    unique quand on tourne dans une `UnitOfWork` — c'est ce qui permet de partager
    la même transaction que les autres repos (cf. `_executor.acquire`).
    """

    def __init__(self, executor: Executor):
        self._executor = executor

    async def create(
        self, player_id: int, room_id: int | None, mode: GameMode
    ) -> Game:
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                f"INSERT INTO games (player_id, room_id, mode, score, status) "
                f"VALUES ($1, $2, $3, $4, $5) RETURNING {_GAME_SELECT_COLS}",
                player_id,
                room_id,
                mode.value,
                0,
                GameStatus.PLAYING.value,
            )
        return row_to_game(dict(row))

    async def get_by_id(self, id: int) -> Game | None:
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                f"SELECT {_GAME_SELECT_COLS} FROM games WHERE id = $1",
                id,
            )
        return row_to_game(dict(row) if row is not None else None)

    async def add_points(self, game_id: int, points: int) -> Game:
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                f"UPDATE games SET score = score + $1 WHERE id = $2 "
                f"RETURNING {_GAME_SELECT_COLS}",
                points,
                game_id,
            )
        return row_to_game(dict(row))

    async def get_active_by_room(self, room_id: int) -> list[Game]:
        async with acquire(self._executor) as conn:
            rows = await conn.fetch(
                f"SELECT {_GAME_SELECT_COLS} FROM games "
                f"WHERE room_id = $1 AND status = $2",
                room_id,
                GameStatus.PLAYING.value,
            )
        return [row_to_game(dict(r)) for r in rows]

    async def finish(self, game_id: int) -> Game:
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                f"UPDATE games SET status = $1, finished_at = NOW() WHERE id = $2 "
                f"RETURNING {_GAME_SELECT_COLS}",
                GameStatus.FINISHED.value,
                game_id,
            )
        return row_to_game(dict(row))

    async def leaderboard(
        self,
        mode: GameMode | None,
        limit: int,
    ) -> list[LeaderboardEntry]:
        params: list = [GameStatus.FINISHED.value]
        sql = (
            "SELECT p.id AS player_id, p.pseudo AS pseudo, MAX(g.score) AS score "
            "FROM games g "
            "JOIN players p ON g.player_id = p.id "
            "WHERE g.status = $1"
        )
        if mode is not None:
            params.append(mode.value)
            sql += f" AND g.mode = ${len(params)}"
        params.append(int(limit))
        # Un joueur = son meilleur score (MAX), d'où le GROUP BY. Le tri secondaire
        # sur p.id départage les ex æquo de façon stable : à scores égaux, le
        # classement ne bouge pas d'une requête à l'autre.
        sql += (
            f" GROUP BY p.id, p.pseudo ORDER BY score DESC, p.id ASC "
            f"LIMIT ${len(params)}"
        )

        async with acquire(self._executor) as conn:
            rows = await conn.fetch(sql, *params)
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
        async with acquire(self._executor) as conn:
            rows = await conn.fetch(
                f"SELECT {_GAME_SELECT_COLS} FROM games "
                f"WHERE status = $1 ORDER BY started_at DESC",
                status.value,
            )
        return [row_to_game(dict(r)) for r in rows]

    async def get_finished_games_by_player(
        self,
        player_id: int,
        mode: GameMode | None,
        limit: int,
    ) -> list[Game]:
        params: list = [player_id, GameStatus.FINISHED.value]
        sql = (
            f"SELECT {_GAME_SELECT_COLS} FROM games "
            f"WHERE player_id = $1 AND status = $2"
        )
        if mode is not None:
            params.append(mode.value)
            sql += f" AND mode = ${len(params)}"
        params.append(int(limit))
        sql += f" ORDER BY finished_at DESC, id DESC LIMIT ${len(params)}"

        async with acquire(self._executor) as conn:
            rows = await conn.fetch(sql, *params)
        return [row_to_game(dict(r)) for r in rows]

    async def get_best_solo_score(self, player_id: int) -> int | None:
        async with acquire(self._executor) as conn:
            row = await conn.fetchrow(
                "SELECT MAX(score) AS best FROM games "
                "WHERE player_id = $1 AND mode = $2 AND status = $3",
                player_id,
                GameMode.SOLO.value,
                GameStatus.FINISHED.value,
            )
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
        """Écrit en base une partie terminée + ses events, en une seule transaction.

        Tout est atomique : on retrouve le joueur (ou on le crée), on insère la
        partie finie, puis ses events. Si une étape échoue, rien n'est persisté —
        pas de partie orpheline sans events ni l'inverse.
        """
        event_rows = self._build_event_rows(events)
        async with acquire(self._executor) as conn:
            async with conn.transaction():
                player_id = await self._upsert_player(conn, pseudo)
                game_id = await self._insert_finished_game(
                    conn, player_id, mode, score, started_at, finished_at
                )
                inserted_events = await self._insert_event_rows(conn, game_id, event_rows)
        return player_id, game_id, inserted_events

    @staticmethod
    def _build_event_rows(events: list[dict[str, Any]]) -> list[tuple]:
        """Transforme les events bruts du buffer Redis en tuples insérables.

        Tolérant aux données imparfaites venues du réseau : un topic inconnu est
        ignoré, des points illisibles retombent à 0, une date absente ou invalide
        est remplacée par l'instant courant. On préfère persister une partie un peu
        approximative que de tout perdre sur un event malformé.
        """
        rows: list[tuple] = []
        for ev in events:
            topic = ev.get("topic")
            event_type = _TOPIC_TO_EVENT_TYPE.get(topic) if isinstance(topic, str) else None
            if event_type is None:
                continue  # topic non mappé → on laisse tomber cet event
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
            # Colonnes TIMESTAMP sans fuseau : asyncpg refuse les datetimes tz-aware,
            # on retire donc le fuseau avant insertion.
            if occured_at.tzinfo is not None:
                occured_at = occured_at.replace(tzinfo=None)
            rows.append((event_type.value, points, occured_at))
        return rows

    @staticmethod
    async def _upsert_player(conn: asyncpg.Connection, pseudo: str) -> int:
        row = await conn.fetchrow(
            "SELECT id FROM players WHERE pseudo = $1",
            pseudo,
        )
        if row is not None:
            return row["id"]
        row = await conn.fetchrow(
            "INSERT INTO players (pseudo) VALUES ($1) RETURNING id",
            pseudo,
        )
        return row["id"]

    @staticmethod
    async def _insert_finished_game(
        conn: asyncpg.Connection,
        player_id: int,
        mode: GameMode,
        score: int,
        started_at: datetime,
        finished_at: datetime,
    ) -> int:
        # asyncpg TIMESTAMP (without TZ) doesn't accept tz-aware datetimes.
        if started_at.tzinfo is not None:
            started_at = started_at.replace(tzinfo=None)
        if finished_at.tzinfo is not None:
            finished_at = finished_at.replace(tzinfo=None)
        row = await conn.fetchrow(
            "INSERT INTO games (player_id, room_id, mode, score, status, started_at, finished_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
            player_id,
            None,
            mode.value,
            score,
            GameStatus.FINISHED.value,
            started_at,
            finished_at,
        )
        return row["id"]

    @staticmethod
    async def _insert_event_rows(
        conn: asyncpg.Connection, game_id: int, event_rows: list[tuple]
    ) -> int:
        if not event_rows:
            return 0
        rows_with_game = [(game_id,) + row for row in event_rows]
        await conn.executemany(
            "INSERT INTO game_events (game_id, type, points, occured_at) "
            "VALUES ($1, $2, $3, $4)",
            rows_with_game,
        )
        return len(rows_with_game)
