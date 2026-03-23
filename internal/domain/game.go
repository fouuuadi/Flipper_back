package domain

import "time"

type GameMode string
type GameStatus string

const (
	GameModeSolo GameMode = "solo"
	GameMode1v1  GameMode = "1v1"
)

const (
	GameStatusPlaying  GameStatus = "playing"
	GameStatusFinished GameStatus = "finished"
)

type Game struct {
	ID         int64      `json:"id"`
	MatchID    *int64     `json:"match_id,omitempty"`
	PlayerID   int64      `json:"player_id"`
	Mode       GameMode   `json:"mode"`
	Score      int64      `json:"score"`
	Status     GameStatus `json:"status"`
	StartedAt  time.Time  `json:"started_at"`
	FinishedAt *time.Time `json:"finished_at,omitempty"`
}
