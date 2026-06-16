from app.domain.game import GameMode
from app.domain.ports.matchmaking_repository import MatchmakingRepository
from app.domain.ports.room_repository import RoomRepository
from app.domain.ports.game_repository import GameRepository
        

class MatchmakingUseCase:
    def __init__(
        self,
        matchmaking_repo: MatchmakingRepository,
        room_repo: RoomRepository,
        game_repo: GameRepository,
    ):
        self.matchmaking_repo = matchmaking_repo
        self.room_repo = room_repo
        self.game_repo = game_repo

    async def execute(
        self,
        player_id: int,
        mode: str,
    ) -> dict:

        opponent = await self.matchmaking_repo.claim_waiting_player(
            player_id=player_id,
            mode=mode,
        )

        if opponent:

            room = await self.room_repo.create(GameMode.ONE_V_ONE)

            game1 = await self.game_repo.create(
                player_id=opponent.player1_id,
                room_id=room.id,
            )

            game2 = await self.game_repo.create(
                player_id=player_id,
                room_id=room.id,
            )

            return {
                "status": "matched",
                "room_code": room.code,
                "game_ids": [game1.id, game2.id],
            }

        matchmaking = await self.matchmaking_repo.create(
            player_id=player_id,
            mode=mode,
        )

        return {
            "status": "waiting",
            "matchmaking_id": matchmaking.id,
        }