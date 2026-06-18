from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class BorneNavState(str, Enum):
    """Phase de navigation partagée par les 3 écrans de la borne.

    `in_game` est l'ombrelle sous laquelle circulent les events de match
    (`match:state`, `score:update`…) ; la session de jeu, elle, est suivie
    séparément sur l'entité `Session`.
    """

    SPLASH = "splash"
    MENU = "menu"
    IDENTIFICATION = "identification"
    BOUTIQUE = "boutique"
    SETTINGS = "settings"
    LEADERBOARD = "leaderboard"
    IN_GAME = "in_game"
    GAME_OVER = "game_over"


class Borne(BaseModel):
    """État partagé d'une borne (playfield + backglass + dmd).

    Permanente : créée au premier accès, elle vit du boot à l'extinction. Elle
    porte la phase de navigation courante et, le cas échéant, la session de jeu
    active. C'est la source de vérité broadcastée à tous les écrans.
    """

    borne_id: str
    nav: BorneNavState = BorneNavState.SPLASH
    active_session_id: str | None = None
