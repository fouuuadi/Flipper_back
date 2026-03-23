package domain

import "time"

type GameEventType string

const (
	GameEventBumperHit  GameEventType = "bumper_hit"
	GameEventBallLost   GameEventType = "ball_lost"
	GameEventBonus      GameEventType = "bonus"
	GameEventFlipperHit GameEventType = "flipper_hit"
	GameEventGameOver   GameEventType = "game_over"
)

type GameEvent struct {
	ID        int64         `json:"id"`
	GameID    int64         `json:"game_id"`
	Type      GameEventType `json:"type"`
	Points    int64         `json:"points"`
	OccuredAt time.Time     `json:"occured_at"`
}
