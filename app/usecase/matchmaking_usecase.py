from app.domain.exceptions import PlayerNotFoundError, PseudoCollisionInRoomError
from app.domain.game import GameMode
from app.domain.ports.matchmaking_repository import MatchmakingRepository
from app.domain.ports.player_repository import PlayerRepository
from app.domain.ports.room_repository import RoomRepository
from app.domain.ports.game_repository import GameRepository
from app.domain.ports.session_service import SessionService


class MatchmakingUseCase:
    def __init__(
        self,
        matchmaking_repo: MatchmakingRepository,
        room_repo: RoomRepository,
        game_repo: GameRepository,
        player_repo: PlayerRepository,
        session_service: SessionService,
    ):
        self.matchmaking_repo = matchmaking_repo
        self.room_repo = room_repo
        self.game_repo = game_repo
        self.player_repo = player_repo
        self.session_service = session_service

    async def execute(
        self,
        player_id: int,
        mode: str,
    ) -> dict:

        player = await self.player_repo.get_by_id(player_id)
        if player is None:
            raise PlayerNotFoundError(f"Player {player_id} not found")

        opponent = await self.matchmaking_repo.claim_waiting_player(
            player_id=player_id,
            mode=mode,
        )

        if opponent:
            opponent_player = await self.player_repo.get_by_id(opponent.player1_id)
            if opponent_player is None:
                raise PlayerNotFoundError(f"Player {opponent.player1_id} not found")

            room = await self.room_repo.create(GameMode.ONE_V_ONE)

            # Vérifier unicité des pseudos dans la room (les 2 joueurs ne peuvent pas avoir le même)
            for pseudo in (player.pseudo, opponent_player.pseudo):
                is_unique = await self.session_service.check_pseudo_uniqueness_in_room(
                    room_code=room.code,
                    pseudo=pseudo,
                )
                if not is_unique:
                    raise PseudoCollisionInRoomError(
                        f"Pseudo '{pseudo}' déjà présent dans la room '{room.code}'"
                    )

            game1 = await self.game_repo.create(
                player_id=opponent.player1_id,
                room_id=room.id,
                mode=GameMode.ONE_V_ONE,
            )

            game2 = await self.game_repo.create(
                player_id=player_id,
                room_id=room.id,
                mode=GameMode.ONE_V_ONE,
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